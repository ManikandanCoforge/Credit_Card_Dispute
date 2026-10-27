"""Qualify a model for the hybrid's questions (ADR-003) and, on request, register it.

The tool asks the model the dispute-type question for every case in a qualification
set (evals/qualification), scores each answer with src/model_registry.py, writes the
per-case report and prints the record. --register appends a passed record to
models.toml; a record that fails, or one made from replayed answers, is never registered.

The model comes from the environment as it does for a run (src/model_clients.py),
except that it need not be qualified yet. Each case's lines are the set's recorded
statement lines, so the prompt is the one the record vouches for.

  MODEL_PROVIDER=azure_openai MODEL_ID=gpt-6-luna AZURE_OPENAI_ENDPOINT=...
  AZURE_OPENAI_API_KEY=... python tools/qualify_model.py evals/qualification/cue_suite.json
      --report evals/qualification/reports/azure_openai__gpt-6-luna__cue_suite.json --register

Exit status is 0 only when the record passes.
"""

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model_clients import LIVE_PROVIDERS, REGISTRY, ModelSetupError, model_from_env
from src.model_cue import ModelClient, StatementLine, ask_dispute_type
from src.model_registry import QualificationRecord, QualificationRow, score, summarize
from src.untrusted import redact


def suite_lines(case: Mapping[str, Any]) -> list[StatementLine]:
    """A qualification case's recorded lines, shown to the model with restricted values redacted."""
    return [
        {"source_id": line_id.rsplit(":", 1)[0], "text": text, "shown": redact(text)}
        for line_id, text in case["lines"]
    ]


def qualify(model: ModelClient, suite: Sequence[Mapping[str, Any]]) -> list[QualificationRow]:
    """Ask the dispute-type question for every case and score each answer."""
    rows: list[QualificationRow] = []
    for case in suite:
        answer, call, _why = ask_dispute_type(model, suite_lines(case))
        proposal = None if answer is None else answer["type"]
        rows.append(
            {
                "case_id": case["case_id"],
                "expected": case["expected_class"],
                "gap": bool(case.get("gap")),
                "proposal": proposal,
                "outcome": score(case["expected_class"], proposal),
                "answered": call is not None and call["answered"] and call["error"] is None,
                "latency_ms": None if call is None else call["latency_ms"],
            }
        )
    return rows


def toml_entry(record: QualificationRecord) -> str:
    """One [[model]] table for models.toml. A value that is None is left out."""
    lines = ["[[model]]"]
    for key, value in record.items():
        if value is None:
            continue
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, int | float):
            text = repr(value)
        else:
            text = json.dumps(str(value))
        lines.append(f"{key} = {text}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Run one qualification set, write its report and optionally register the record."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("suite", type=Path, help="A qualification set, such as cue_suite.json.")
    parser.add_argument("--report", type=Path, required=True, help="Where to write the report.")
    parser.add_argument("--register", action="store_true", help="Append a passed record.")
    parser.add_argument("--registry", type=Path, default=REGISTRY, help="The models.toml path.")
    parser.add_argument("--approved-by", default="", help="Who approved this model's use.")
    parser.add_argument("--data-location", default="", help="Where the provider served calls.")
    args = parser.parse_args(argv)
    try:
        model = model_from_env(os.environ, require_qualified=False)
    except ModelSetupError as error:
        print(f"the model cannot be used: {error}", file=sys.stderr)
        return 1
    if model is None:
        print("set MODEL_PROVIDER and the model's settings first", file=sys.stderr)
        return 1
    if args.register and model.provider not in LIVE_PROVIDERS:
        print("only a live model's run is registered, never a replayed one", file=sys.stderr)
        return 1
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    rows = qualify(model, suite)
    record = summarize(
        rows,
        provider=model.provider,
        model_id=model.model,
        qualified_on=date.today().isoformat(),
        data_location=args.data_location,
        approved_by=args.approved_by,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps({"entry": record, "cases": rows}, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{record['provider']}/{record['model_id']}: {record['cue_correct']} correct, "
        f"{record['cautious']} cautious, {record['unsafe']} unsafe of {record['cases']}; "
        f"{'passed' if record['passed'] else 'failed'}"
    )
    if args.register and record["passed"]:
        with args.registry.open("a", encoding="utf-8") as stream:
            stream.write("\n" + toml_entry(record))
        print(f"registered in {args.registry}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
