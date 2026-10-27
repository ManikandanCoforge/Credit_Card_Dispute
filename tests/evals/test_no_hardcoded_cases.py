"""No case identifier may be baked into the suite."""

from __future__ import annotations

from evals.dataset import REPO_ROOT

FORBIDDEN = "CARD-D"


def test_evals_source_contains_no_development_case_identifier():
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "evals").rglob("*.py")):
        if FORBIDDEN in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []
