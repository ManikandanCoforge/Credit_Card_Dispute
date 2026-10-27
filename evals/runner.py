"""Run the application once over one dataset and collect everything a metric needs."""

from __future__ import annotations

# Runs git rev-parse for the run identity.
import subprocess  # nosec B404
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.contract import CaseOutcome, RunData
from evals.dataset import REPO_ROOT, SuiteError, format_errors, load_dataset, load_gold
from evals.mockbank import read_audit, running_mock


def run_evaluation(data_dir: Path, gold_path: Path, set_name: str) -> RunData:
    """Build the run record for one dataset: outcomes, audit and run identity."""
    data_dir = Path(data_dir)
    dataset = load_dataset(data_dir)
    gold = load_gold(gold_path)
    _require_matching_ids(dataset, gold)
    with tempfile.TemporaryDirectory(
        prefix="eval-mock-", ignore_cleanup_errors=True
    ) as temporary:
        state_path = Path(temporary) / "mock.sqlite"
        with running_mock(data_dir, state_path) as base_url:
            results = _build_contracts(base_url, data_dir)
            audit = read_audit(state_path)
    by_id = {str(result["case_id"]): result for result in results}
    cases: list[CaseOutcome] = []
    for case in dataset["cases"]:
        case_id = str(case["case_id"])
        result = by_id.get(case_id, {})
        cases.append(
            CaseOutcome(
                case_id=case_id,
                tools=tuple(str(tool) for tool in case["tools"]),
                documents=tuple(str(document) for document in case["documents"]),
                gold=gold[case_id],
                contract=result.get("contract"),
                build_error=result.get("error"),
                audit=tuple(row for row in audit if row.get("case_id") == case_id),
            )
        )
    return RunData(
        set_name=set_name,
        data_dir=data_dir,
        gold_path=Path(gold_path),
        dataset=dataset,
        gold=gold,
        sources=dataset["sources"],
        cases=tuple(cases),
        audit=tuple(audit),
        format_errors=format_errors(dataset, results),
        commit=_commit(),
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        base_url="local mock",
    )


def _build_contracts(base_url: str, data_dir: Path) -> list[dict[str, Any]]:
    """Call the application once for the whole case list, in bank order."""
    from src.contract_records import CaseListError, load_contract_results

    try:
        results = load_contract_results(base_url, data_dir)
    except CaseListError as error:
        raise SuiteError(f"the bank case list could not be read: {error}") from error
    return [dict(result) for result in results]


def _require_matching_ids(
    dataset: Mapping[str, Any], gold: Mapping[str, Mapping[str, Any]]
) -> None:
    """Fail before running when the dataset and gold disagree about the case set."""
    dataset_ids = {str(case["case_id"]) for case in dataset["cases"]}
    gold_ids = set(gold)
    if dataset_ids != gold_ids:
        missing = sorted(dataset_ids - gold_ids)
        extra = sorted(gold_ids - dataset_ids)
        raise SuiteError(f"dataset and gold disagree: missing gold {missing}, extra gold {extra}")


def _commit() -> str:
    """Return the short commit the run was produced from, or `unknown`."""
    try:
        # Fixed argv, git from PATH.
        completed = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return completed.stdout.strip() or "unknown"
