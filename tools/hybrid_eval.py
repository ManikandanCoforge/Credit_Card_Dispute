"""Evaluate the hybrid against the rules alone, suite by suite, with the bank's own evaluator.

For each suite the tool starts the unmodified mock (tools/runtime.py) on a fresh state,
runs every case through the production read path, and scores the submission array with
tools.evaluate.evaluate. Each suite runs twice, each time on a fresh mock: first with no
model, then with the model the environment names (MODEL_PROVIDER; see
src/model_clients.py). The report compares passed cases, wrong drafts marked ready,
cases sent to manual review, cases not built, and model calls and tokens.

Suites: dev (data/dev with feedback/dev_gold.json) and the synthetic suites in
evals/fixtures: synth, stress and holdout. With MODEL_PROVIDER=replay and
MODEL_REPLAY=evals/recordings/gpt-6-luna.jsonl it runs offline on recorded answers.

  MODEL_PROVIDER=replay MODEL_REPLAY=evals/recordings/gpt-6-luna.jsonl
  python tools/hybrid_eval.py

On Windows, run it with PYTHONUTF8=1: the vendored evaluator reads files in the locale
encoding, and one synthetic merchant name is not ASCII. Exit status is 0 when every
run completed, whatever its score; the numbers are the result.
"""

import argparse
import json
import os

# Starts the repository's own mock as a child process.
import subprocess  # nosec B404
import sys
import tempfile
import time
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.contract_records import (
    ContractResult,
    build_contract_result,
    contract_case_plans,
)
from src.model_clients import ModelSetupError, model_from_env
from src.model_cue import ModelClient
from tools.evaluate import evaluate

FIXTURES = ROOT / "evals" / "fixtures"
SUITES: dict[str, tuple[Path, Path]] = {
    "dev": (ROOT / "data" / "dev", ROOT / "feedback" / "dev_gold.json"),
    **{
        name: (FIXTURES / name / "data", FIXTURES / name / "gold.json")
        for name in ("synth", "stress", "holdout")
    },
}


@contextmanager
def mock(data_dir: Path, port: int) -> Iterator[str]:
    """The unmodified mock serving one suite on a fresh state, stopped afterwards.

    Windows can hold the state file for a moment after the mock stops, so a failed
    clean-up of the temporary state is ignored rather than failing the run.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as state_dir:
        # Fixed argv: this interpreter and tools/runtime.py, never a shell.
        process = subprocess.Popen(  # nosec B603
            [
                sys.executable,
                str(ROOT / "tools" / "runtime.py"),
                "serve",
                "--data",
                str(data_dir),
                "--state",
                str(Path(state_dir) / "state.sqlite"),
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            _wait_for(base_url)
            yield base_url
        finally:
            process.terminate()
            process.wait()


def run_pass(data_dir: Path, port: int, model: ModelClient | None) -> list[ContractResult]:
    """Every case in one suite, through the production read path, on a fresh mock."""
    with mock(data_dir, port) as base_url:
        plans = contract_case_plans(base_url, data_dir)
        return [build_contract_result(plan, base_url, data_dir, model=model) for plan in plans]


def summarize_pass(
    results: Sequence[ContractResult], evaluation: Mapping[str, Any]
) -> dict[str, Any]:
    """One run's numbers. A wrong draft marked ready is a ready draft the evaluator failed."""
    passed = {case["case_id"]: bool(case["passed"]) for case in evaluation["cases"]}
    checks = {case["case_id"]: case["checks"] for case in evaluation["cases"]}
    built = [result for result in results if result["contract"] is not None]
    calls = [call for result in results for call in result["model_calls"]]
    return {
        "passed": sum(passed.values()),
        "total": len(passed),
        "failed": {
            case_id: sorted(name for name, ok in checks[case_id].items() if not ok)
            for case_id, ok in sorted(passed.items())
            if not ok
        },
        "not_built_reasons": {
            result["case_id"]: result["error"] for result in results if result["contract"] is None
        },
        "wrong_ready": sorted(
            result["case_id"]
            for result in built
            if result["contract"] is not None
            and result["contract"]["routing"] == "ready_for_review"
            and not passed.get(result["case_id"], False)
        ),
        "manual_review": sum(
            1
            for result in built
            if result["contract"] is not None
            and result["contract"]["routing"] == "manual_review"
        ),
        "not_built": sorted(result["case_id"] for result in results if result["contract"] is None),
        "format_errors": list(evaluation["format_errors"]),
        "model_calls": len(calls),
        "model_answers": sum(1 for call in calls if call["answered"] and call["error"] is None),
        "input_tokens": sum(call["input_tokens"] or 0 for call in calls),
        "output_tokens": sum(call["output_tokens"] or 0 for call in calls),
    }


def evaluate_suite(name: str, model: ModelClient, port: int) -> dict[str, Any]:
    """The rules alone and the hybrid on one suite, each scored by the bank's evaluator."""
    data_dir, gold_path = SUITES[name]
    dataset = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    report: dict[str, Any] = {"suite": name}
    for label, used in (("rules", None), ("hybrid", model)):
        results = run_pass(data_dir, port, used)
        submissions = [result["contract"] for result in results if result["contract"] is not None]
        report[label] = summarize_pass(results, evaluate(dataset, gold, submissions))
    return report


def render_table(reports: Sequence[Mapping[str, Any]]) -> str:
    """A plain-text comparison: one row per suite and design."""
    header = (
        f"{'Suite':8} {'Design':7} {'Passed':>9} {'Wrong ready':>12} {'Manual':>7} "
        f"{'Not built':>10} {'Calls':>6} {'Tokens in/out':>15}"
    )
    lines = [header, "-" * len(header)]
    for report in reports:
        for label in ("rules", "hybrid"):
            row = report[label]
            lines.append(
                f"{report['suite']:8} {label:7} {row['passed']:>4} / {row['total']:<3} "
                f"{len(row['wrong_ready']):>12} {row['manual_review']:>7} "
                f"{len(row['not_built']):>10} {row['model_calls']:>6} "
                f"{row['input_tokens']:>7}/{row['output_tokens']:<7}"
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Evaluate the chosen suites and write the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suites", nargs="+", choices=sorted(SUITES), default=list(SUITES))
    parser.add_argument(
        "--report", type=Path, default=ROOT / "evals" / "reports" / "hybrid-eval.json"
    )
    parser.add_argument("--port", type=int, default=8901)
    args = parser.parse_args(argv)
    try:
        model = model_from_env(os.environ)
    except ModelSetupError as error:
        print(f"the model cannot be used: {error}", file=sys.stderr)
        return 1
    if model is None:
        print("set MODEL_PROVIDER (for example replay with MODEL_REPLAY) first", file=sys.stderr)
        return 1
    reports = [evaluate_suite(name, model, args.port) for name in args.suites]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps({"model": f"{model.provider}/{model.model}", "suites": reports}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"Model: {model.provider}/{model.model}\n{render_table(reports)}")
    return 0


def _wait_for(base_url: str) -> None:
    deadline = time.monotonic() + 15
    while True:
        try:
            # base_url is http://127.0.0.1 on the --port mock() was given, never a file: URL.
            with urllib.request.urlopen(f"{base_url}/health", timeout=1):  # nosec B310
                return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
