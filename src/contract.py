"""Map one working record onto the evaluation output contract.

assemble_contract is pure: every piece of evidence arrives as text, so the
classification, the deadline and the citation slices can be checked without a
bank. The case runner in src/contract_records.py does the reading.

A contract that the supplied sources cannot support - no policy version for the
reported date, a rule line missing from the procedure, a quote that is not in its
source - raises ContractError instead of being paraphrased.
"""

import json
from datetime import date, timedelta
from typing import TypedDict

from src.models import Intake, Transaction, WorkingRecord

# build_records stores an absent intake line as these words, never as an empty value.
_ABSENT = "not supplied"
_DENIED = "denied"
_UNAUTHORIZED_DAYS_LABEL = "Unauthorized deadline days:"
_UNAUTHORIZED_RULE_ANCHOR = "Use unauthorized"
_ROUTING_RULE_ANCHOR = "Routing precedence:"
_AMOUNT_LABEL = "Amount:"
_SOURCE_ID_LABEL = "Source ID:"


class Facts(TypedDict):
    transaction_id: str | None
    amount: int | None
    currency: str | None
    reported_date: str | None


class Citation(TypedDict):
    claim: str
    source_id: str
    quote: str


class FollowUpQuestion(TypedDict):
    field: str
    question: str


class Contract(TypedDict):
    case_id: str
    classification: str
    routing: str
    policy_ids: list[str]
    facts: Facts
    missing_information: list[str]
    deadline: str | None
    citations: list[Citation]
    follow_up_questions: list[FollowUpQuestion]
    narrative: str


class ContractError(Exception):
    """A working record cannot become a contract object that its sources support."""


def assemble_contract(
    record: WorkingRecord,
    *,
    intake_text: str,
    attachment_text: str,
    procedure_text: str,
    policy_text: str,
    transactions_text: str,
) -> Contract:
    """Return the contract object for one working record.

    Amount and currency are read from the transaction named on the intake, never
    from the attachment. A named transaction that the tool did not return leaves
    both facts null; the keys stay present.

    transactions_text is the transactions tool body as the evaluator stores it:
    json.dumps(body, sort_keys=True). The named charge is cited from it as one
    sorted JSON object, so the amount and currency are tied to that transaction.

    The deadline is the reported date plus the policy's unauthorized day count,
    with the reported day as day zero.

    Citations are exact slices of the four supplied sources. A slice that cannot
    be made exactly raises ContractError.
    """
    intake = record["intake"]
    if intake is None:
        raise ContractError("the working record has no intake")
    classification = _classification(intake)
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractError("the reported date selected no policy version")
    reported = _day(intake["reported_date"])
    if reported is None:
        raise ContractError("the intake has no reported date")
    if record["missing_information"]:
        raise ContractError("missing information needs targeted questions first")
    deadline, deadline_quote = _deadline(reported, policy_text)
    procedure_source = _source_id(procedure_text)
    routing = "ready_for_review"
    citations: list[Citation] = [
        {
            "claim": "customer_evidence",
            "source_id": _source_id(intake_text),
            "quote": _statement(intake, intake_text),
        },
        {
            "claim": "customer_evidence",
            "source_id": _source_id(attachment_text),
            "quote": _unique_line(attachment_text, _AMOUNT_LABEL),
        },
        _transaction_citation(intake["transaction_id"], transactions_text),
        {
            "claim": "classification",
            "source_id": procedure_source,
            "quote": _sentence(procedure_text, _UNAUTHORIZED_RULE_ANCHOR),
        },
        {
            "claim": "routing",
            "source_id": procedure_source,
            "quote": _sentence(procedure_text, _ROUTING_RULE_ANCHOR),
        },
        {
            "claim": "deadline",
            "source_id": _source_id(policy_text),
            "quote": deadline_quote,
        },
    ]
    return {
        "case_id": record["case_id"],
        "classification": classification,
        "routing": routing,
        "policy_ids": [version_id, procedure_id],
        "facts": _facts(intake, record.get("transactions", [])),
        "missing_information": [],
        "deadline": deadline,
        "citations": citations,
        "follow_up_questions": [],
        "narrative": _narrative(record["case_id"], classification, routing, deadline),
    }


def _classification(intake: Intake) -> str:
    """A denied authorization is unauthorized. Other types arrive in a later step."""
    if intake["authorization"] == _DENIED:
        return "unauthorized"
    raise ContractError("only a denied authorization is classified in this step")


def _facts(intake: Intake, transactions: list[Transaction]) -> Facts:
    """The four required facts, with amount and currency from the tool response."""
    transaction_id = None if intake["transaction_id"] == _ABSENT else intake["transaction_id"]
    charge = next(
        (
            row
            for row in transactions
            if transaction_id is not None and row["transaction_id"] == transaction_id
        ),
        None,
    )
    return {
        "transaction_id": transaction_id,
        "amount": None if charge is None else charge["amount"],
        "currency": None if charge is None else charge["currency"],
        "reported_date": intake["reported_date"],
    }


_TRANSACTION_ROW_KEYS = frozenset(
    {"transaction_id", "amount", "currency", "merchant_id", "posted_date"}
)


def _transaction_citation(transaction_id: str, transactions_text: str) -> Citation:
    """Cite the named charge from the tool body, or the body's source id when it is absent.

    The quote is json.dumps(charge, sort_keys=True), which is an exact slice of a
    body that was itself dumped with sorted keys. A row carrying any field outside
    the five the contract cites is refused rather than quoted, so a payload value
    such as a private token cannot ride into a citation.
    """
    try:
        body = json.loads(transactions_text)
        source_id = body["source_id"]
        charges = body["transactions"]
    except (ValueError, TypeError, KeyError) as error:
        raise ContractError("the transactions tool body is not usable") from error
    if not isinstance(source_id, str) or not isinstance(charges, list):
        raise ContractError("the transactions tool body is not usable")
    named = [
        charge
        for charge in charges
        if isinstance(charge, dict) and charge.get("transaction_id") == transaction_id
    ]
    if len(named) == 1:
        charge = named[0]
        if set(charge) != _TRANSACTION_ROW_KEYS:
            raise ContractError("the transaction row is not the five contract fields")
        claim = "transaction_record"
        quote = json.dumps(charge, sort_keys=True)
    else:
        claim = "transaction_service_checked"
        quote = json.dumps({"source_id": source_id})[1:-1]
    if quote not in transactions_text:
        raise ContractError("the transactions tool body is not in sorted-key form")
    return {"claim": claim, "source_id": source_id, "quote": quote}


def _deadline(reported: date, policy_text: str) -> tuple[str, str]:
    """Return the deadline and the policy line it is calculated from."""
    quote = _unique_line(policy_text, _UNAUTHORIZED_DAYS_LABEL)
    days = quote.split(":", 1)[1].strip()
    if not days.isdigit():
        raise ContractError("the unauthorized deadline days are not a number")
    return (reported + timedelta(days=int(days))).isoformat(), quote


def _narrative(case_id: str, classification: str, routing: str, deadline: str) -> str:
    """One deterministic sentence, marked as a draft for the human reviewer."""
    return (
        f"Draft for human review: {case_id} is classified {classification} and routed "
        f"{routing}, with a policy deadline of {deadline}; no case has been created."
    )


def _day(value: str) -> date | None:
    """Parse a YYYY-MM-DD day. An absent field is not a day."""
    if value == _ABSENT:
        return None
    return date.fromisoformat(value)


def _statement(intake: Intake, intake_text: str) -> str:
    """The customer's own words, only when they are quoted exactly from the intake."""
    statement = intake["statement"]
    if statement == _ABSENT or statement not in intake_text:
        raise ContractError("the intake statement is not an exact excerpt of the intake")
    return statement


def _unique_line(text: str, prefix: str) -> str:
    """The one line that starts with prefix, or a loud failure."""
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(prefix)]
    if len(lines) != 1:
        raise ContractError(f"expected exactly one {prefix!r} line in the source")
    return lines[0]


def _sentence(text: str, anchor: str) -> str:
    """The sentence that starts at anchor, exactly as written, line breaks included."""
    start = text.find(anchor)
    if start < 0:
        raise ContractError(f"{anchor!r} is not in the source")
    end = text.find(".", start)
    if end < 0:
        raise ContractError(f"{anchor!r} is not a sentence in the source")
    return text[start : end + 1]


def _source_id(text: str) -> str:
    """The source id the document declares for itself."""
    source_id = _unique_line(text, _SOURCE_ID_LABEL).split(":", 1)[1].strip()
    if not source_id:
        raise ContractError("the source declares no source id")
    return source_id
