"""The demo driver hashes a draft exactly as the bank does, so its changed-draft step is honest.

deploy/poc/record_demo.py shows a changed draft is refused without posting it, by
comparing its hash with the approved one. deploy/ is outside the coverage gate, so this
test keeps that hash from drifting away from the bank's.
"""

import importlib.util
from pathlib import Path

from tools.runtime import digest

ROOT = Path(__file__).resolve().parents[1]


def _record_demo():
    spec = importlib.util.spec_from_file_location(
        "record_demo", ROOT / "deploy" / "poc" / "record_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_demo_hashes_a_draft_exactly_as_the_bank_does():
    draft = {
        "case_id": "CARD-D01",
        "narrative": "Draft for human review: Café Lumen, 117 XCR.",
        "citations": [{"claim": "customer_evidence", "quote": "a", "source_id": "S"}],
        "deadline": None,
    }

    assert _record_demo().draft_hash(draft) == digest(draft)


def test_a_changed_draft_has_a_different_hash():
    draft = {"case_id": "CARD-D01", "routing": "ready_for_review"}

    assert _record_demo().draft_hash({**draft, "demo_tamper": True}) != digest(draft)
