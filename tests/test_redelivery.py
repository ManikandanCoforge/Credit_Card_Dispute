"""CARD-D09, a redelivery of CARD-D02, drafted from the bank like any other complaint.

The supplied mock runs in process on a free port with a temporary state. The draft is
scored by the supplied evaluator against the development answers.
"""

import json
import threading
from contextlib import contextmanager
from pathlib import Path

from src.contract_records import load_contract_results
from tools.evaluate import evaluate
from tools.runtime import create_server

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"


def test_card_d09_redelivery_is_drafted_and_passes_the_supplied_evaluator(tmp_path):
    with _mock(tmp_path) as base_url:
        results = {result["case_id"]: result for result in load_contract_results(base_url, DEV)}

    d09 = results["CARD-D09"]
    assert d09["error"] is None
    contract = d09["contract"]
    assert contract["classification"] == "duplicate_charge"
    assert contract["routing"] == "ready_for_review"
    assert contract["deadline"] == "2026-11-16"
    assert contract["facts"] == {
        "transaction_id": "TX-D02",
        "amount": 134,
        "currency": "XCR",
        "reported_date": "2026-10-02",
    }
    assert "CARD-D09-TRANSACTIONS" in {citation["source_id"] for citation in contract["citations"]}
    dataset = json.loads((DEV / "dataset.json").read_text(encoding="utf-8"))
    gold = json.loads((ROOT / "feedback" / "dev_gold.json").read_text(encoding="utf-8"))
    report = evaluate(dataset, {"CARD-D09": gold["CARD-D09"]}, [contract])
    [scored] = report["cases"]
    assert scored["passed"], scored["checks"]


def test_card_d09_is_not_typed_from_its_delivery_note(tmp_path):
    # The note says the complaint is a redelivery. Whether it is a duplicate record is the
    # bank's to say, through the ledger, so the note never reaches the draft.
    with _mock(tmp_path) as base_url:
        results = {result["case_id"]: result for result in load_contract_results(base_url, DEV)}

    draft = json.dumps(results["CARD-D09"]["contract"])
    assert "Delivery note" not in draft
    assert "redelivery" not in draft


@contextmanager
def _mock(tmp_path):
    server = create_server(DEV, tmp_path / "mock.sqlite", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
