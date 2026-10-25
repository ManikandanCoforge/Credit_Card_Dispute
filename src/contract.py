"""Map one working record onto the evaluation output contract.

assemble_contract is pure: every piece of evidence arrives as text, so the
classification, the deadline and the citation slices can be checked without a
bank. The case runner in src/contract_records.py does the reading.

A contract that the supplied sources cannot support - no policy version for the
reported date, a rule line missing from the procedure, a quote that is not in its
source - raises ContractError instead of being paraphrased.
"""

import json
import re
from collections.abc import Sequence
from datetime import date, timedelta

from src.escalation import (
    Escalation,
    EscalationError,
    find_escalation,
    instruction_holds_cue,
)
from src.models import (
    Citation,
    Contract,
    Facts,
    FollowUpQuestion,
    Intake,
    Transaction,
    WorkingRecord,
)
from src.narrative import NarrativeMeter, ProseWriter, draft_narrative
from src.untrusted import INSTRUCTION_NOTICE, has_instruction, restricted_values

# Contract and FollowUpQuestion now live in src.models; they stay importable from here.
__all__ = [
    "Contract",
    "ContractError",
    "FollowUpQuestion",
    "assemble_contract",
    "assemble_draft",
]

# build_records stores an absent intake line as these words, never as an empty value.
_ABSENT = "not supplied"
_DENIED = "denied"
_UNAUTHORIZED_DAYS_LABEL = "Unauthorized deadline days:"
_UNAUTHORIZED_RULE_ANCHOR = "Use unauthorized"
_ROUTING_RULE_ANCHOR = "Routing precedence:"
_PRECEDENCE_RULE_ANCHOR = "Manual review takes precedence"
_EFFECTIVE_FROM_LABEL = "Effective from:"
_EFFECTIVE_THROUGH_LABEL = "Effective through:"
_AMOUNT_LABEL = "Amount:"
_SOURCE_ID_LABEL = "Source ID:"
_MANUAL_REVIEW = "manual_review"
_DUPLICATE_DAYS_LABEL = "Duplicate deadline days:"
_DUPLICATE_RULE_ANCHOR = "Use duplicate_charge"
_DAYS_LABELS = {
    "unauthorized": _UNAUTHORIZED_DAYS_LABEL,
    "duplicate_charge": _DUPLICATE_DAYS_LABEL,
}
_RULE_ANCHORS = {
    "unauthorized": _UNAUTHORIZED_RULE_ANCHOR,
    "duplicate_charge": _DUPLICATE_RULE_ANCHOR,
}
# The customer's report of two charges for one purchase, and its negation.
# "twice" counts only beside a charging verb ("charged me 236 crowns twice"); "I called
# twice" or "I called about the charge twice" is not a report of two charges.
_DUPLICATE = re.compile(
    r"\b(?:charged|billed|debited|deducted|took|taken)\b[^.!?]*\btwice\b"
    r"|\bsame (?:charge|payment|transaction)\b[^.!?]*\btwice\b"
    r"|\btwo (?:identical |separate )?(?:charges|debits|payments)\b|\bdouble[- ]?(?:charg|bill)\w*"
    r"|\bduplicate (?:charges?|transactions?|payments?)\b|\bcharged (?:me )?(?:two|2) times\b",
    re.IGNORECASE,
)
_NOT_DUPLICATE = re.compile(
    r"\bnot (?:a |an )?(?:double|duplicate)\b|\bnot (?:charged )?twice\b", re.IGNORECASE
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A complaint that gives a dispute detail inside text addressed to the system.
_INSTRUCTION_ESCALATION: Escalation = {
    "classification": "ambiguous",
    "reason": (
        "A customer statement gives a dispute detail inside text addressed to the system. "
        "That text is not read for the dispute type, so a person must classify the case. "
        "It was treated as evidence and not followed."
    ),
    "citations": [],
}

# One targeted question per missing field that the contract allows.
_QUESTIONS = {
    "authorization_confirmation": (
        "Can you confirm whether you authorized the card transaction named in your complaint?"
    ),
    "promised_service_date": "On what date did the merchant promise to supply the service?",
    "purchase_receipt": "Can you send the receipt or order confirmation for this purchase?",
}
# The fields each classification requires: "Required fields absent for the chosen type
# must all be requested." Every intake form carries every field, so a blank field that
# another type would need is not requested. ambiguous is the procedure's conflict about
# authorization, so it needs authorization_confirmation; unsupported names no field.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "unauthorized": ("authorization_confirmation",),
    "service_not_received": ("promised_service_date", "purchase_receipt"),
    "duplicate_charge": (),
    "ambiguous": ("authorization_confirmation",),
    "unsupported": (),
}


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
    customer_texts: Sequence[str] = (),
) -> Contract:
    """Return the contract object for one working record, with the template narrative.

    This path uses no model. See assemble_draft for the arguments.
    """
    contract, _meter = assemble_draft(
        record,
        intake_text=intake_text,
        attachment_text=attachment_text,
        procedure_text=procedure_text,
        policy_text=policy_text,
        transactions_text=transactions_text,
        customer_texts=customer_texts,
    )
    return contract


def assemble_draft(
    record: WorkingRecord,
    *,
    intake_text: str,
    attachment_text: str,
    procedure_text: str,
    policy_text: str,
    transactions_text: str,
    customer_texts: Sequence[str] = (),
    writer: ProseWriter | None = None,
) -> tuple[Contract, NarrativeMeter]:
    """Return the contract object for one working record, and how its narrative was made.

    Every field except narrative comes from the rules below and never from the
    writer. A writer may only reword the template narrative; see src/narrative.py.

    customer_texts are further customer statements about the complaint, such as
    a follow-up email. A cash withdrawal, or customer statements that conflict
    about authorization, escalate the complaint before it is classified: see
    src/escalation.py.

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
    contract, notes = _rules_contract(
        record,
        intake_text=intake_text,
        attachment_text=attachment_text,
        procedure_text=procedure_text,
        policy_text=policy_text,
        transactions_text=transactions_text,
        customer_texts=customer_texts,
    )
    narrative, meter = draft_narrative(contract, notes, writer)
    return {**contract, "narrative": narrative}, meter


def _rules_contract(
    record: WorkingRecord,
    *,
    intake_text: str,
    attachment_text: str,
    procedure_text: str,
    policy_text: str,
    transactions_text: str,
    customer_texts: Sequence[str],
) -> tuple[Contract, list[str]]:
    """The contract with an empty narrative, and the notes its narrative must carry."""
    intake = record["intake"]
    if intake is None:
        raise ContractError("the working record has no intake")
    try:
        escalation = find_escalation(intake_text, list(customer_texts), procedure_text)
    except EscalationError as error:
        raise ContractError(str(error)) from error
    # Text addressed to the system is never read for a cue, and dropping it must not
    # hide one: when it holds a cue, a person classifies the case. So such text can
    # only ever send a case to a person, never choose its class or make it ready.
    statements = [intake_text, *customer_texts]
    if escalation is None and instruction_holds_cue(statements, _DUPLICATE):
        escalation = _INSTRUCTION_ESCALATION
    if escalation is not None:
        return _escalated_contract(
            record,
            intake,
            escalation,
            intake_text=intake_text,
            attachment_text=attachment_text,
            procedure_text=procedure_text,
            policy_text=policy_text,
            transactions_text=transactions_text,
        )
    classification = _classification(intake)
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractError("the reported date selected no policy version")
    reported = _day(intake["reported_date"])
    if reported is None:
        raise ContractError("the intake has no reported date")
    if _required_missing(record, classification):
        raise ContractError("missing information needs targeted questions first")
    deadline, deadline_quote = _deadline(reported, policy_text, classification)
    procedure_source = _source_id(procedure_text)
    routing = "ready_for_review"
    second_charges = (
        _other_charge_citations(
            intake["statement"], intake["transaction_id"], transactions_text
        )
        if classification == "duplicate_charge"
        else []
    )
    citations: list[Citation] = [
        _customer_evidence(intake, intake_text),
        {
            "claim": "customer_evidence",
            "source_id": _source_id(attachment_text),
            "quote": _unique_line(attachment_text, _AMOUNT_LABEL),
        },
        _transaction_citation(intake["transaction_id"], transactions_text),
        *second_charges,
        {
            "claim": "classification",
            "source_id": procedure_source,
            "quote": _sentence(procedure_text, _RULE_ANCHORS[classification]),
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
    contract: Contract = {
        "case_id": record["case_id"],
        "classification": classification,
        "routing": routing,
        "policy_ids": [version_id, procedure_id],
        "facts": _facts(intake, record.get("transactions", [])),
        "missing_information": [],
        "deadline": deadline,
        "citations": citations,
        "follow_up_questions": [],
        "narrative": "",
    }
    return contract, _untrusted_notes(record)


def _escalated_contract(
    record: WorkingRecord,
    intake: Intake,
    escalation: Escalation,
    *,
    intake_text: str,
    attachment_text: str,
    procedure_text: str,
    policy_text: str,
    transactions_text: str,
) -> tuple[Contract, list[str]]:
    """A complaint the procedure sends to a human.

    Routing is manual_review and the deadline is null. Policy ids, facts and the
    transaction citation are kept, because the escalation does not skip the
    work. The missing fields this classification requires are still listed,
    each with one question, because manual review outranks missing-information
    routing without hiding it.
    """
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractError("the reported date selected no policy version")
    missing = _required_missing(record, escalation["classification"])
    procedure_source = _source_id(procedure_text)
    policy_source = _source_id(policy_text)
    escalation_citations: list[Citation] = [
        {"claim": quote["claim"], "source_id": quote["source_id"], "quote": quote["quote"]}
        for quote in escalation["citations"]
    ]
    citations: list[Citation] = [
        _customer_evidence(intake, intake_text),
        _attachment_citation(attachment_text),
        _transaction_citation(intake["transaction_id"], transactions_text),
        *escalation_citations,
        {
            "claim": "routing",
            "source_id": procedure_source,
            "quote": _unique_line(procedure_text, _ROUTING_RULE_ANCHOR),
        },
        {
            "claim": "policy_selection",
            "source_id": policy_source,
            "quote": _unique_line(policy_text, _EFFECTIVE_FROM_LABEL),
        },
        {
            "claim": "policy_selection",
            "source_id": policy_source,
            "quote": _unique_line(policy_text, _EFFECTIVE_THROUGH_LABEL),
        },
    ]
    if missing:
        citations.append(
            {
                "claim": "routing",
                "source_id": procedure_source,
                "quote": _sentence(procedure_text, _PRECEDENCE_RULE_ANCHOR),
            }
        )
    contract: Contract = {
        "case_id": record["case_id"],
        "classification": escalation["classification"],
        "routing": _MANUAL_REVIEW,
        "policy_ids": [version_id, procedure_id],
        "facts": _facts(intake, record.get("transactions", [])),
        "missing_information": missing,
        "deadline": None,
        "citations": citations,
        "follow_up_questions": [
            {"field": field, "question": _QUESTIONS[field]} for field in missing
        ],
        "narrative": "",
    }
    return contract, [escalation["reason"], *_untrusted_notes(record)]


def _attachment_citation(attachment_text: str) -> Citation:
    """The attachment's Amount line when it has exactly one, otherwise its Source ID line.

    Escalation does not rest on the amount, so an attachment without a single
    Amount line (D12's shape) must not stop the case from being drafted.
    """
    source_id = _source_id(attachment_text)
    amounts = [
        line.strip()
        for line in attachment_text.splitlines()
        if line.strip().startswith(_AMOUNT_LABEL)
    ]
    if len(amounts) == 1:
        quote = amounts[0]
    else:
        quote = _unique_line(attachment_text, _SOURCE_ID_LABEL)
    return {"claim": "customer_evidence", "source_id": source_id, "quote": quote}


def _required_missing(record: WorkingRecord, classification: str) -> list[str]:
    """The record's missing fields that the classification requires, in record order.

    A field outside the contract's allowed set is a contract error, never dropped.
    """
    for field in record["missing_information"]:
        if field not in _QUESTIONS:
            raise ContractError(f"no question is defined for the missing field {field!r}")
    required = _REQUIRED_FIELDS[classification]
    return [field for field in record["missing_information"] if field in required]


def _classification(intake: Intake) -> str:
    """A denied authorization is unauthorized; two charges for one purchase is duplicate_charge.

    A sentence written as an instruction is not read, so "classify this as a
    double charge" in the customer's text cannot choose the class. Other types
    arrive in a later step.
    """
    if intake["authorization"] == _DENIED:
        return "unauthorized"
    sentences = [
        sentence
        for sentence in _SENTENCE_END.split(intake["statement"])
        if not has_instruction(sentence) and not _NOT_DUPLICATE.search(sentence)
    ]
    if any(_DUPLICATE.search(sentence) for sentence in sentences):
        return "duplicate_charge"
    raise ContractError("only unauthorized and duplicate_charge are classified in this step")


def _customer_evidence(intake: Intake, intake_text: str) -> Citation:
    """The customer's own words, quoted exactly; the intake's Source ID line when they hold a
    restricted value (a card number the customer typed), so the case is drafted, not refused.
    """
    statement = _statement(intake, intake_text)
    if restricted_values(statement):
        statement = _unique_line(intake_text, _SOURCE_ID_LABEL)
    return {"claim": "customer_evidence", "source_id": _source_id(intake_text), "quote": statement}


def _other_charge_citations(
    statement: str, transaction_id: str, transactions_text: str
) -> list[Citation]:
    """Cite the second charge of a duplicate, so both transaction records are on file.

    At most one row is cited. It must be the five contract fields and either be named
    by the customer, or match the named charge's merchant, amount and currency and be
    posted within two days of it. Any other row, even one of the same amount, is
    unrelated and is never quoted; a row with extra fields is skipped, not fatal.
    """
    source_id, charges = _tool_charges(transactions_text)
    named = next((c for c in charges if c.get("transaction_id") == transaction_id), None)
    if named is None:
        return []
    candidates = [
        charge
        for charge in charges
        if isinstance(charge.get("transaction_id"), str)
        and charge.get("transaction_id") != transaction_id
        and set(charge) == _TRANSACTION_ROW_KEYS
    ]
    ranked = [c for c in candidates if _named_in(str(c["transaction_id"]), statement)] + [
        c for c in candidates if _same_charge(c, named)
    ]
    if not ranked:
        return []
    return [{"claim": "second_charge", "source_id": source_id, "quote": _row_quote(ranked[0])}]


def _named_in(transaction_id: str, statement: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(transaction_id)}(?![\w-])", statement) is not None


def _same_charge(charge: dict[str, object], named: dict[str, object]) -> bool:
    """Same merchant, amount and currency as the named charge, posted within two days."""
    if any(charge.get(k) != named.get(k) for k in ("merchant_id", "amount", "currency")):
        return False
    try:
        gap = date.fromisoformat(str(charge.get("posted_date"))) - date.fromisoformat(
            str(named.get("posted_date"))
        )
    except ValueError:
        return False
    return abs(gap.days) <= 2


def _untrusted_notes(record: WorkingRecord) -> list[str]:
    """A warning for the reviewer when the merchant text is written as instructions."""
    merchant = record.get("merchant")
    if merchant is not None and has_instruction(merchant["note"]):
        return [INSTRUCTION_NOTICE]
    return []


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
    source_id, charges = _tool_charges(transactions_text)
    named = [charge for charge in charges if charge.get("transaction_id") == transaction_id]
    if len(named) == 1:
        claim = "transaction_record"
        quote = _row_quote(named[0])
    else:
        claim = "transaction_service_checked"
        quote = json.dumps({"source_id": source_id})[1:-1]
    if quote not in transactions_text:
        raise ContractError("the transactions tool body is not in sorted-key form")
    return {"claim": claim, "source_id": source_id, "quote": quote}


def _row_quote(charge: dict[str, object]) -> str:
    """One transaction row as a sorted JSON quote, only when it is exactly the five contract fields.

    Every row that is quoted, the named charge and a duplicate's second charge
    alike, passes through here, so no extra payload field can reach a citation.
    """
    if set(charge) != _TRANSACTION_ROW_KEYS:
        raise ContractError("the transaction row is not the five contract fields")
    return json.dumps(charge, sort_keys=True)


def _tool_charges(transactions_text: str) -> tuple[str, list[dict[str, object]]]:
    """The source id and the charge objects of a transactions tool body."""
    try:
        body = json.loads(transactions_text)
        source_id = body["source_id"]
        charges = body["transactions"]
    except (ValueError, TypeError, KeyError) as error:
        raise ContractError("the transactions tool body is not usable") from error
    if not isinstance(source_id, str) or not isinstance(charges, list):
        raise ContractError("the transactions tool body is not usable")
    return source_id, [charge for charge in charges if isinstance(charge, dict)]


def _deadline(reported: date, policy_text: str, classification: str) -> tuple[str, str]:
    """Return the deadline and the policy line it is calculated from."""
    quote = _unique_line(policy_text, _DAYS_LABELS[classification])
    days = quote.split(":", 1)[1].strip()
    if not days.isdigit():
        raise ContractError("the deadline days are not a number")
    return (reported + timedelta(days=int(days))).isoformat(), quote


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
