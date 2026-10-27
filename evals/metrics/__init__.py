"""Metric registry: one module per primary eval, all deterministic and offline."""

from __future__ import annotations

from collections.abc import Iterable

from evals.contract import Check, RunData
from evals.metrics import conformance, escalation, grounding, pii, tools

MODULES = (conformance, grounding, tools, escalation, pii)
"""Every metric module, in report order."""

NAMES = tuple(module.NAME for module in MODULES)


def run_metrics(run: RunData, enabled: Iterable[str] | None = None) -> list[Check]:
    """Run the selected metrics and return their checks in module order."""
    selected = set(NAMES if enabled is None else enabled)
    unknown = selected - set(NAMES)
    if unknown:
        raise ValueError(f"unknown metrics: {sorted(unknown)}")
    checks: list[Check] = []
    for module in MODULES:
        if module.NAME in selected:
            checks.extend(module.run(run))
    return checks
