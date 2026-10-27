"""Read a suite file, the dataset and the gold file, and check their shape.

Case identifiers come from the dataset and the gold file. Nothing here knows a
case by name, so the same code runs the development set and an injected hidden
set.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
"""Repository root: suite paths are written relative to it."""

SUITE_KEYS = frozenset({"name", "data", "gold", "metrics", "gates"})


class SuiteError(ValueError):
    """A suite, dataset or gold file cannot be read as this suite expects."""


def load_suite(path: Path) -> dict[str, Any]:
    """Read a suite file and resolve its data and gold paths against the repo root."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise SuiteError(f"cannot read suite {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SuiteError(f"suite {path} is not JSON: {error}") from error
    if not isinstance(raw, dict):
        raise SuiteError("a suite must be a JSON object")
    unknown = set(raw) - SUITE_KEYS
    if unknown:
        raise SuiteError(f"unknown suite keys: {sorted(unknown)}")
    for key in ("name", "data", "gold"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise SuiteError(f"suite needs a non-empty {key}")
    metrics = raw.get("metrics", [])
    if not isinstance(metrics, list) or not all(isinstance(x, str) for x in metrics):
        raise SuiteError("suite metrics must be a list of names")
    gates = raw.get("gates", {})
    if not isinstance(gates, dict) or not all(
        isinstance(k, str) and isinstance(v, (int, float)) for k, v in gates.items()
    ):
        raise SuiteError("suite gates must map a metric to a minimum rate")
    return {
        "name": raw["name"],
        "data": REPO_ROOT / raw["data"],
        "gold": REPO_ROOT / raw["gold"],
        "metrics": metrics,
        "gates": gates,
    }


def load_dataset(data_dir: Path) -> dict[str, Any]:
    """Read dataset.json and require the keys the runner and metrics rely on."""
    path = Path(data_dir) / "dataset.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SuiteError(f"cannot read dataset {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SuiteError(f"dataset {path} is not JSON: {error}") from error
    if not isinstance(raw, dict):
        raise SuiteError("dataset.json must be a JSON object")
    cases, sources = raw.get("cases"), raw.get("sources")
    if not isinstance(cases, list) or not cases:
        raise SuiteError("dataset.json needs a non-empty cases list")
    if not isinstance(sources, dict) or not sources:
        raise SuiteError("dataset.json needs a non-empty sources mapping")
    identifiers: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise SuiteError("every dataset case needs a string case_id")
        if not isinstance(case.get("tools"), dict):
            raise SuiteError(f"{case['case_id']} needs a tools mapping")
        if not isinstance(case.get("documents"), list):
            raise SuiteError(f"{case['case_id']} needs a documents list")
        identifiers.append(case["case_id"])
    if len(set(identifiers)) != len(identifiers):
        raise SuiteError("dataset case ids must be unique")
    if not all(isinstance(text, str) for text in sources.values()):
        raise SuiteError("every dataset source must be a string")
    return raw


def load_gold(path: Path) -> dict[str, Mapping[str, Any]]:
    """Read the gold file and require one mapping per case."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise SuiteError(f"cannot read gold {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SuiteError(f"gold {path} is not JSON: {error}") from error
    if not isinstance(raw, dict) or not raw:
        raise SuiteError("gold must be a non-empty object keyed by case id")
    if not all(isinstance(value, dict) for value in raw.values()):
        raise SuiteError("every gold entry must be an object")
    return raw


def format_errors(
    dataset: Mapping[str, Any], results: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    """Return structural problems with the submission, never a scoring opinion."""
    expected = [case["case_id"] for case in dataset["cases"]]
    seen: list[str] = []
    errors: list[str] = []
    for result in results:
        case_id = result.get("case_id")
        if not isinstance(case_id, str):
            errors.append("a result has no string case_id")
            continue
        if case_id in seen:
            errors.append(f"duplicate result: {case_id}")
        seen.append(case_id)
        contract = result.get("contract")
        if contract is not None and not isinstance(contract, dict):
            errors.append(f"contract is not an object: {case_id}")
    for case_id in expected:
        if case_id not in seen:
            errors.append(f"missing result: {case_id}")
    for case_id in seen:
        if case_id not in expected:
            errors.append(f"unexpected result: {case_id}")
    return tuple(errors)
