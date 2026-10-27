"""Offline, deterministic evaluation suite for the Lumen dispute handler.

The suite is spec-driven: a suite file names the dataset, the gold file and
the metrics to run. It starts the supplied mock, runs the application once,
reads the mock audit, and writes a JSON artifact plus a Markdown report.

The shape is derived from the eval-harness project (MIT): spec, case set,
per-case checks with evidence, and a Wilson interval per metric. The harness
core is trimmed to what an offline deterministic suite needs, so no database,
console, credential store or judge is required here.
"""

from evals.contract import CaseOutcome, Check, RunData

__all__ = ["CaseOutcome", "Check", "RunData"]
