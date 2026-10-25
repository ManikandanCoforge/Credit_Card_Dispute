"""The draft narrative: evidence, uncertainty, recommendation, limitations, customer reply.

The template path is the default. It needs no model and no network, and it only
restates values the rules already computed. A configured ProseWriter may reword
that template, and nothing else: it never sees the evidence, and its text is used
only when it keeps every section in order, adds no date, number or id the
template did not contain, makes no promise and carries no restricted value.
Otherwise the template is kept. Either way, the rule-computed contract fields
are untouched, because the writer only ever returns the narrative string.

CARD-PROCEDURE-01: "No promise of refund, success, reimbursement, or
eligibility. Communications are drafts for human review."
"""

import re
import time
from collections.abc import Callable, Sequence
from typing import TypedDict

from src.models import Contract
from src.untrusted import restricted_values

# Rewrites the template draft. It receives the template text and nothing else.
ProseWriter = Callable[[str], str]

SECTIONS = ("Evidence:", "Uncertainty:", "Recommendation:", "Limitations:")
REPLY_MARKER = "Customer reply (DRAFT, not sent):"
_PROMISE = re.compile(
    r"\brefund|\breimburs|\bguarantee|\beligib|\bapproved\b|\bsuccess"
    r"|\bmoney back\b|\bwill be (?:credited|returned|reversed|resolved)\b",
    re.IGNORECASE,
)
# Dates, ids and numbers: the facts a reworded draft must not invent.
_FACT_TOKEN = re.compile(r"\d{4}-\d{2}-\d{2}|[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+|\d+(?:\.\d+)?")
_ACTIONS = {
    "ready_for_review": "A reviewer can check the cited evidence and decide.",
    "request_information": "Ask the customer the follow-up questions before review.",
    "manual_review": "A person must decide this case; the draft does not.",
}


class NarrativeMeter(TypedDict):
    narrative_path: str
    narrative_latency_ms: float
    model_calls: int


def draft_narrative(
    contract: Contract,
    notes: Sequence[str] = (),
    writer: ProseWriter | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[str, NarrativeMeter]:
    """Return the narrative for a contract and how it was produced.

    The path is "template", "model", or "template_fallback" when the writer
    failed or its text broke a rule. Latency covers the whole step on every path.

    A writer reports failure by raising OSError (network), ValueError (bad output)
    or RuntimeError (refusal or other provider error). Any other exception is a bug
    and stops the case rather than being hidden.
    """
    started = clock()
    template = template_narrative(contract, notes)
    text, path, calls = template, "template", 0
    if writer is not None:
        calls = 1
        try:
            reworded = writer(template)
        except (OSError, ValueError, RuntimeError):
            reworded = None
        if reworded is not None and not narrative_problems(reworded, template):
            text, path = reworded, "model"
        else:
            path = "template_fallback"
    latency_ms = round((clock() - started) * 1000, 3)
    return text, {"narrative_path": path, "narrative_latency_ms": latency_ms, "model_calls": calls}


def template_narrative(contract: Contract, notes: Sequence[str] = ()) -> str:
    """The deterministic draft, built only from the contract's own fields and the notes."""
    facts = contract["facts"]
    transaction = facts["transaction_id"] or "not named"
    if facts["amount"] is None:
        observed = (
            "The transaction service did not return the named transaction, so amount and "
            "currency are left empty."
        )
    else:
        observed = f"The transaction service shows {facts['amount']} {facts['currency']}."
    sources = ", ".join(dict.fromkeys(c["source_id"] for c in contract["citations"]))
    evidence = (
        f"Evidence: {contract['case_id']} reports transaction {transaction}, reported "
        f"{facts['reported_date']}. {observed} Cited sources: {sources}."
    )
    doubts = list(notes)
    if contract["missing_information"]:
        doubts.append(
            "Missing information is still requested: "
            f"{', '.join(contract['missing_information'])}."
        )
    uncertainty = "Uncertainty: " + (" ".join(doubts) or "None found in the cited sources.")
    if contract["deadline"] is None:
        timing = "No deadline is set because the procedure gives none for this classification."
    else:
        timing = f"The policy deadline is {contract['deadline']}."
    recommendation = (
        f"Recommendation: classified {contract['classification']} under "
        f"{', '.join(contract['policy_ids'])} and routed {contract['routing']}. {timing} "
        f"{_ACTIONS.get(contract['routing'], _ACTIONS['manual_review'])}"
    )
    limitations = (
        "Limitations: prepared only from the cited documents and tool data under the "
        "fictional bank procedure; no card-network or legal rules were used. No case has been "
        "created: a person must approve this exact draft first, and any change needs a new "
        "approval."
    )
    questions = " ".join(q["question"] for q in contract["follow_up_questions"])
    reply = (
        f"{REPLY_MARKER} Thank you for contacting Lumen Bank about transaction {transaction}. "
        "Your report is with our dispute team for review."
        + (f" To continue, please answer: {questions}" if questions else "")
        + " We cannot confirm an outcome yet."
    )
    return (
        f"Draft for human review.\n{evidence}\n{uncertainty}\n"
        f"{recommendation}\n{limitations}\n{reply}"
    )


def narrative_problems(text: str, template: str) -> list[str]:
    """Every rule a draft breaks. A template draft breaks none."""
    problems: list[str] = []
    positions = [text.find(marker) for marker in (*SECTIONS, REPLY_MARKER)]
    if -1 in positions or positions != sorted(positions):
        problems.append("the four sections and the draft reply are not all present in order")
    if _PROMISE.search(text):
        problems.append("the draft makes a promise")
    if restricted_values(text):
        problems.append("the draft carries a restricted value")
    if set(_FACT_TOKEN.findall(text)) - set(_FACT_TOKEN.findall(template)):
        problems.append("the draft states a date, number or id the template did not")
    return problems
