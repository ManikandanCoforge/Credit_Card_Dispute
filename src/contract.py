"""Map one working record onto the evaluation output contract.

assemble_contract is pure: every piece of evidence arrives as text, so the
classification, the deadline and the citation slices can be checked without a
bank. The case runner in src/contract_records.py does the reading.

A contract that the supplied sources cannot support - no policy version for the
reported date, a rule line missing from the procedure, a quote that is not in its
source - raises ContractError instead of being paraphrased.

A supported classification is emitted even when evidence is missing: the draft is
routed to request_information and carries one targeted question per absent field.
"""

import json
import re
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta

from src.escalation import (
    Escalation,
    EscalationError,
    find_escalation,
    instruction_holds_cue,
)
from src.model_cue import (
    DisputeType,
    ModelCall,
    ModelClient,
    StatementLine,
    ask_dispute_type,
    ask_multiple_problems,
    statement_lines,
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
from src.untrusted import (
    ATTACHMENT_INSTRUCTION_NOTICE,
    INSTRUCTION_NOTICE,
    STATEMENT_INSTRUCTION_NOTICE,
    addresses_a_model,
    has_instruction,
    restricted_values,
    visible,
)

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
_CONFIRMED = "confirmed"
_UNAUTHORIZED_DAYS_LABEL = "Unauthorized deadline days:"
_DUPLICATE_DAYS_LABEL = "Duplicate deadline days:"
_SERVICE_DAYS_LABEL = "Service deadline days:"
_UNAUTHORIZED_RULE_ANCHOR = "Use unauthorized"
_DUPLICATE_RULE_ANCHOR = "Use duplicate_charge"
_SERVICE_RULE_ANCHOR = "Use service_not_received"
_ROUTING_RULE_ANCHOR = "Routing precedence:"
_PRECEDENCE_RULE_ANCHOR = "Manual review takes precedence"
_EFFECTIVE_FROM_LABEL = "Effective from:"
_EFFECTIVE_THROUGH_LABEL = "Effective through:"
_AMOUNT_LABEL = "Amount:"
_ATTACHMENT_STATUS_LABEL = "Attachment status:"
_SOURCE_ID_LABEL = "Source ID:"
_MANUAL_REVIEW = "manual_review"
# The customer's report of two charges for one purchase, and its negation.
# "twice" counts only beside a charging verb ("charged me 236 crowns twice"), when the
# charge itself appears twice ("my charge appears twice on my statement") or when it was
# put through twice; "I called twice" or "I called about the charge twice" is not a
# report of two charges.
_DUPLICATE = re.compile(
    r"\b(?:charged|billed|debited|deducted|took|taken|ran)\b[^.!?]*\btwice\b"
    r"|\bput\b[^.!?]*\bthrough\b[^.!?]*\btwice\b"
    r"|\b(?:charge|payment|transaction|debit|bill)s?\b[^.!?]*"
    r"\b(?:appears?|appeared|shows?|showed|shown|listed|posted|went through)\b[^.!?]*\btwice\b"
    r"|\bsame (?:charge|payment|transaction)\b[^.!?]*\btwice\b"
    r"|\btwo (?:identical |separate )?(?:charges|debits|payments)\b|\bdouble[- ]?(?:charg|bill)\w*"
    r"|\bduplicate (?:charges?|transactions?|payments?)\b|\bcharged (?:me )?(?:two|2) times\b",
    re.IGNORECASE,
)
# A denial of the duplicate itself is not a report of one. It is checked on the same
# sentence as the cue, so "charged twice, not a double charge" stays reported.
_NOT_DUPLICATE = re.compile(
    r"\bnot (?:a |an )?(?:double|duplicate)\b|\bnot (?:charged )?(?:twice|two times|2 times)\b"
    r"|(?:\bnot|n't|\bnever)\s+(?:appear\w*|show\w*|listed|posted|go through|went through)"
    r"\b[^.!?]{0,30}\btwice\b"
    r"|\b(?:not|never|no)\b[^.!?]{0,25}\b(?:charged|billed|debited)\b[^.!?]{0,25}"
    r"\b(?:twice|two times|2 times)\b"
    r"|(?:\bnot|n't|\bnever|\bno)\s+(?:(?:see|find|have|notice|show)\w*\s+)?(?:any\s+)?"
    r"two\s+(?:identical\s+|separate\s+)?(?:charges|debits|payments)\b"
    r"|\b(?:not|never|no)\b\s+(?:a\s+|an\s+|the\s+)?"
    r"(?:double|duplicate)[- ]?(?:charge|charges|transaction|transactions|payment|payments)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A complaint that gives a dispute detail inside text addressed to the system.
_INSTRUCTION_REASON = (
    "A customer statement gives a dispute detail inside text addressed to the system. "
    "That text is not read for the dispute type, so a person must classify the case. "
    "It was treated as evidence and not followed."
)
# A duplicate needs both charges: "retrieve both transaction records".
_ONE_CHARGE_NOTE = (
    "Only one charge for this purchase is on record, and the procedure asks for both "
    "transaction records, so a person must find the second charge before this draft is used."
)
# The transaction service did not answer within the procedure's three attempts.
_RETRY_RULE_ANCHOR = "Retry a transient failure"
_UNAVAILABLE_FACTS_ANCHOR = "If that service remains unavailable"
_UNAVAILABLE_NOTE = (
    "The transaction service did not answer within the procedure's three attempts, so "
    "amount and currency are unknown, not zero, and no transaction record is cited. "
    "A person must review this case."
)
# The hybrid's escalations (ADR-003). A model answer can send a case to a person; it never
# makes a case ready by itself.
_MULTIPLE_PROBLEMS_ESCALATION: Escalation = {
    "classification": "ambiguous",
    "reason": (
        "A model check suggests the complaint describes more than one problem, so no single "
        "type is set and a person decides."
    ),
    "citations": [],
}
_NO_TYPE_REASON = (
    "Neither the rules nor the model could name a dispute type, so a person must classify "
    "the case."
)
_AUTHORIZATION_LABEL = "Authorization:"
_AMBIGUOUS_RULE_ANCHOR = "If customer accounts conflict about authorization"
_UNSUPPORTED_RULE_ANCHOR = "Cash withdrawal disputes are unsupported"
_SUPPORTED_RULE_ANCHOR = "Supported classifications:"

# The procedure sentence that supports each classification this step can choose.
_CLASSIFICATION_ANCHOR = {
    "unauthorized": _UNAUTHORIZED_RULE_ANCHOR,
    "duplicate_charge": _DUPLICATE_RULE_ANCHOR,
    "service_not_received": _SERVICE_RULE_ANCHOR,
}

# The one policy line that supplies each supported type's day count.
_DEADLINE_LABEL = {
    "unauthorized": _UNAUTHORIZED_DAYS_LABEL,
    "duplicate_charge": _DUPLICATE_DAYS_LABEL,
    "service_not_received": _SERVICE_DAYS_LABEL,
}

# A customer sentence that reports a service or delivery that did not happen.
_SERVICE_NOT_DELIVERED = (
    "not been delivered",
    "not delivered",
    "not received",
    "never arrived",
    "never delivered",
    "service was not supplied",
    "service not supplied",
    "service was never supplied",
)
_SERVICE = re.compile("|".join(re.escape(p) for p in _SERVICE_NOT_DELIVERED), re.IGNORECASE)
# A filing command is not the customer's account of the facts. src.untrusted catches text
# addressed to the system; these are the commands that try to choose the case's class.
# A command has the shape "file this as …" or "mark this complaint as …": a bare "I want to
# record this complaint" is the customer's account. A negated command ("do not mark this as
# resolved") orders nothing, unless its own clause names a class ("do not mark this as a
# duplicate charge"): then there is no account to read, only the sender naming the class.
_INSTRUCTION_SENTENCE = re.compile(
    r"\b(?:system override"
    r"|(?:file|classify|mark|treat|record)\s+(?:this|it)"
    r"(?:\s+(?:complaint|case|dispute|charge|transaction|report))?\s+(?:as|under)"
    r"|ignore (?:all |the )?(?:above|previous|earlier)"
    r"|disregard (?:all |the )?(?:above|previous|earlier))\b",
    re.IGNORECASE,
)
_NEGATED_BEFORE = re.compile(r"\b(?:do\s+not|don't|dont|never|not)\s+$", re.IGNORECASE)
_CLAUSE_END = re.compile(r"[,;:.!?]")
# The fields each classification requires: "Required fields absent for the chosen type
# must all be requested." Every intake form carries every field, so a blank field that
# another type would need stays out. ambiguous is the procedure's conflict about
# authorization, so it needs authorization_confirmation; unsupported names no field.
_REQUIRED_MISSING_INFORMATION: dict[str, tuple[str, ...]] = {
    "unauthorized": ("authorization_confirmation",),
    "duplicate_charge": (),
    "service_not_received": ("promised_service_date", "purchase_receipt"),
    "ambiguous": ("authorization_confirmation",),
    "unsupported": (),
}

# Reads the intake field each missing-information identifier stands for.
_INTAKE_VALUE_BY_MISSING_FIELD: dict[str, Callable[[Intake], str]] = {
    "authorization_confirmation": lambda intake: intake["authorization"],
    "promised_service_date": lambda intake: intake["promised_service_date"],
    "purchase_receipt": lambda intake: intake["purchase_receipt"],
}

# The one targeted question asked for each missing-information identifier. Questions
# name the evidence to supply and never promise an outcome.
_QUESTION_BY_MISSING_FIELD = {
    "authorization_confirmation": (
        "Can you confirm whether you authorized the named card purchase?"
    ),
    "promised_service_date": (
        "What date did the merchant promise to deliver the service?"
    ),
    "purchase_receipt": "Can you provide the purchase receipt for this transaction?",
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
    transactions_text: str | None,
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
    transactions_text: str | None,
    customer_texts: Sequence[str] = (),
    writer: ProseWriter | None = None,
    model: ModelClient | None = None,
    model_calls: list[ModelCall] | None = None,
    known_values: Sequence[str] = (),
) -> tuple[Contract, NarrativeMeter]:
    """Return the contract object for one working record, and how its narrative was made.

    Every field except narrative comes from the rules below and never from the
    writer. A writer may only reword the template narrative; see src/narrative.py.

    model, when given, may answer the two closed questions in src/model_cue.py
    (ADR-003): the dispute type, only when the rules find none, and whether the
    customer describes more than one problem, only once a complete draft would be marked
    ready. Its answer can fill the rules' gap or send the case to a person; every other
    field is still computed here. See _model_lines for when it is never asked. Each call
    is appended to model_calls when a list is given.

    known_values are restricted values known for this case, such as the merchant's
    private token and the customer reference. A customer sentence holding one is cited
    by its Source ID line, as one holding a card number is, so the output guard in
    src/contract_records.py never has to refuse the draft, and what a model is shown
    never holds one.

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
    transactions_text is None when the transaction service stayed unavailable after
    its attempts. Then amount and currency are null, no transactions source is cited
    (none was read), the procedure's retry and null-facts sentences are cited instead,
    and the case routes to manual_review with its deadline still calculated.

    The deadline is the reported date plus the policy's per-type day count, with the
    reported day as day zero. It is calculated for a supported classification even
    when evidence is missing.

    Missing information starts from the working record in its procedure order, keeps
    only the fields the chosen classification requires, and adds any required field
    that the record left out. Each field gets exactly one targeted question, and a
    field the intake supplies is refused rather than questioned. Routing is
    request_information when any field is missing and ready_for_review otherwise. A
    duplicate whose second charge is not on record goes to manual_review instead,
    because the procedure asks for both transaction records.

    Citations are exact slices of the supplied sources. A slice that cannot be
    made exactly raises ContractError.
    """
    contract, notes = _rules_contract(
        record,
        intake_text=intake_text,
        attachment_text=attachment_text,
        procedure_text=procedure_text,
        policy_text=policy_text,
        transactions_text=transactions_text,
        customer_texts=customer_texts,
        model=model,
        calls=[] if model_calls is None else model_calls,
        known=known_values,
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
    transactions_text: str | None,
    customer_texts: Sequence[str],
    model: ModelClient | None,
    calls: list[ModelCall],
    known: Sequence[str],
) -> tuple[Contract, list[str]]:
    """The contract with an empty narrative, and the notes its narrative must carry."""
    intake = record["intake"]
    if intake is None:
        raise ContractError("the working record has no intake")
    try:
        escalation = find_escalation(intake_text, list(customer_texts), procedure_text, known)
    except EscalationError as error:
        raise ContractError(str(error)) from error
    # Text addressed to the system is never read for a cue, and dropping it must not
    # hide one: when it holds a cue, a person classifies the case. So such text can
    # only ever send a case to a person, never choose its class or make it ready.
    statements = [intake_text, *customer_texts]
    if escalation is None:
        escalation = _instruction_escalation(statements)
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
            known=known,
        )
    notes: list[str] = []
    model_citations: list[Citation] = []
    provisional = False
    classification = _classification(intake)
    if classification is None:
        # The rules found no type. A configured model may name one (ADR-003); without a
        # usable answer the case stays unbuilt, as it is when no model is configured.
        lines = None if model is None else _model_lines(statements, known)
        if model is None or lines is None:
            raise ContractError("the intake supports no supported classification")
        answer, call, why = ask_dispute_type(model, lines)
        if call is not None:
            calls.append(call)
        if answer is None:
            raise ContractError(
                "the intake supports no supported classification, and the model gave no "
                f"usable answer: {why}"
            )
        if answer["type"] != "none":
            notes.append(
                f"Classification is model-assisted: {model.provider}/{model.model} read line "
                f"{answer['label']} as {answer['type']}. Verify that line before approving."
            )
        model_escalation = _model_escalation(answer, intake, statements, procedure_text, known)
        if model_escalation is not None:
            return _escalated_contract(
                record,
                intake,
                model_escalation,
                intake_text=intake_text,
                attachment_text=attachment_text,
                procedure_text=procedure_text,
                policy_text=policy_text,
                transactions_text=transactions_text,
                known=known,
                notes=notes,
            )
        classification = answer["type"]
        model_citations.append(
            _line_quote("model_assisted_classification", answer["line"], statements, known)
        )
        # A line the model reads as a denial, on a form that neither denies nor confirms
        # authorization, is the procedure's provisional unauthorized: confirmation is
        # requested, so the model's reading alone never makes a draft ready.
        provisional = classification == "unauthorized" and _form_authorization(intake) != _DENIED
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractError("the reported date selected no policy version")
    reported = _day(intake["reported_date"])
    if reported is None:
        raise ContractError("the intake has no reported date")
    missing_information, follow_up_questions = _missing_information(
        record, intake, classification, attachment_text
    )
    if provisional and "authorization_confirmation" not in missing_information:
        missing_information.append("authorization_confirmation")
        follow_up_questions.append(
            {
                "field": "authorization_confirmation",
                "question": _QUESTION_BY_MISSING_FIELD["authorization_confirmation"],
            }
        )
    routing = "request_information" if missing_information else "ready_for_review"
    deadline, deadline_quote = _deadline(reported, policy_text, classification)
    procedure_source = _source_id(procedure_text)
    second_charges = (
        _other_charge_citations(
            intake["statement"], intake["transaction_id"], transactions_text
        )
        if classification == "duplicate_charge" and transactions_text is not None
        else []
    )
    if transactions_text is None:
        routing = _MANUAL_REVIEW
        notes.append(_UNAVAILABLE_NOTE)
    elif classification == "duplicate_charge" and not second_charges:
        routing = _MANUAL_REVIEW
        notes.append(_ONE_CHARGE_NOTE)
    citations: list[Citation] = [
        _customer_evidence(intake, intake_text, known),
        _attachment_citation(attachment_text, missing_information),
        *_transaction_citations(intake["transaction_id"], transactions_text, procedure_text),
        *second_charges,
        *model_citations,
        {
            "claim": "classification",
            "source_id": procedure_source,
            "quote": _sentence(procedure_text, _CLASSIFICATION_ANCHOR[classification]),
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
    if transactions_text is None and missing_information:
        citations.append(
            {
                "claim": "routing",
                "source_id": procedure_source,
                "quote": _sentence(procedure_text, _PRECEDENCE_RULE_ANCHOR),
            }
        )
    contract: Contract = {
        "case_id": record["case_id"],
        "classification": classification,
        "routing": routing,
        "policy_ids": [version_id, procedure_id],
        "facts": _facts(intake, record.get("transactions", [])),
        "missing_information": missing_information,
        "deadline": deadline,
        "citations": citations,
        "follow_up_questions": follow_up_questions,
        "narrative": "",
    }
    # Instruction text without a dispute cue is dropped from the customer's account; the
    # reviewer is told it was there, as for the merchant record and the attachment.
    if any(has_instruction(text) or _is_command(text) for text in statements):
        notes.append(STATEMENT_INSTRUCTION_NOTICE)
    if routing == "ready_for_review" and model is not None:
        # Once a complete draft would be marked ready, a configured model is asked whether
        # the customer describes more than one problem. A yes can only send the case to a
        # person; the model's own line, when it chose the type, stays cited.
        lines = _model_lines(statements, known)
        if lines is not None:
            multiple, call = ask_multiple_problems(model, lines)
            if call is not None:
                calls.append(call)
            if multiple:
                escalation = {**_MULTIPLE_PROBLEMS_ESCALATION, "citations": [*model_citations]}
                return _escalated_contract(
                    record,
                    intake,
                    escalation,
                    intake_text=intake_text,
                    attachment_text=attachment_text,
                    procedure_text=procedure_text,
                    policy_text=policy_text,
                    transactions_text=transactions_text,
                    known=known,
                    notes=notes,
                )
    return contract, [*notes, *_untrusted_notes(record, attachment_text)]


def _instruction_escalation(statements: Sequence[str]) -> Escalation | None:
    """The escalation for a dispute detail given inside text addressed to the system.

    Each statement holding such text is cited by its Source ID line, so the reviewer
    sees where it was found; the text itself is never quoted.
    """
    holders = [
        text
        for text in statements
        if instruction_holds_cue([text], _DUPLICATE, _SERVICE) or _command_holds_cue([text])
    ]
    if not holders:
        return None
    return {
        "classification": "ambiguous",
        "reason": _INSTRUCTION_REASON,
        "citations": [
            {
                "claim": "instruction_text",
                "source_id": _source_id(text),
                "quote": _unique_line(text, _SOURCE_ID_LABEL),
            }
            for text in holders
        ],
    }


def _escalated_contract(
    record: WorkingRecord,
    intake: Intake,
    escalation: Escalation,
    *,
    intake_text: str,
    attachment_text: str,
    procedure_text: str,
    policy_text: str,
    transactions_text: str | None,
    known: Sequence[str],
    notes: Sequence[str] = (),
) -> tuple[Contract, list[str]]:
    """A complaint the procedure sends to a human.

    Routing is manual_review and the deadline is null. Policy ids, facts and the
    transaction citation are kept, because the escalation does not skip the
    work. The missing fields this classification requires are still listed,
    each with one question, because manual review outranks missing-information
    routing without hiding it. An unavailable transaction service is cited and
    noted the same way as for a supported classification.
    """
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractError("the reported date selected no policy version")
    missing, questions = _missing_information(
        record, intake, escalation["classification"], attachment_text
    )
    procedure_source = _source_id(procedure_text)
    policy_source = _source_id(policy_text)
    escalation_citations: list[Citation] = [
        {"claim": quote["claim"], "source_id": quote["source_id"], "quote": quote["quote"]}
        for quote in escalation["citations"]
    ]
    citations: list[Citation] = [
        _customer_evidence(intake, intake_text, known),
        _attachment_citation(attachment_text, missing, escalated=True),
        *_transaction_citations(intake["transaction_id"], transactions_text, procedure_text),
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
        "follow_up_questions": questions,
        "narrative": "",
    }
    unavailable = [_UNAVAILABLE_NOTE] if transactions_text is None else []
    return contract, [
        escalation["reason"],
        *notes,
        *unavailable,
        *_untrusted_notes(record, attachment_text),
    ]


def _attachment_citation(
    attachment_text: str, missing_information: list[str], *, escalated: bool = False
) -> Citation:
    """The attachment evidence the draft cites.

    A supplied receipt is cited by its Amount line. When the receipt is missing, the
    attachment's status line is cited instead, so a missing-evidence draft still quotes
    the attachment exactly. That holds whatever the classification requires: an
    attachment that declares itself missing ("Attachment status: missing") is cited by
    that line even for a type that does not request a receipt. An escalated case does
    not rest on the amount, so there, and for a missing receipt without a single status
    line, the Source ID line is cited. Any other attachment without a single Amount
    line is refused, including a supplied one whose status line says "attached".
    """
    receipt_missing = "purchase_receipt" in missing_information
    amounts = _lines_starting(attachment_text, _AMOUNT_LABEL)
    statuses = _lines_starting(attachment_text, _ATTACHMENT_STATUS_LABEL)
    if receipt_missing and len(statuses) == 1:
        quote = statuses[0]
    elif not receipt_missing and len(amounts) == 1:
        quote = amounts[0]
    elif _declares_missing(statuses):
        quote = statuses[0]
    elif receipt_missing or escalated:
        quote = _unique_line(attachment_text, _SOURCE_ID_LABEL)
    else:
        quote = _unique_line(attachment_text, _AMOUNT_LABEL)
    return {"claim": "customer_evidence", "source_id": _source_id(attachment_text), "quote": quote}


def _lines_starting(text: str, prefix: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith(prefix)]


def _missing_information(
    record: WorkingRecord, intake: Intake, classification: str, attachment_text: str
) -> tuple[list[str], list[FollowUpQuestion]]:
    """The missing fields the classification requires, each with one targeted question.

    The working record's list comes first, in its procedure order, keeping only the
    fields the classification requires; a required field the record left out is
    added after it. A listed field the intake supplies, or an identifier outside the
    contract's allowed set, is refused rather than questioned. An attachment that
    declares itself missing governs over an intake that says the receipt is attached,
    so the receipt is then requested when the classification requires it.
    """
    asked = _follow_up_questions(intake, list(record["missing_information"]))
    required = _required_missing(_receipt_as_declared(intake, attachment_text), classification)
    missing = [q["field"] for q in asked if q["field"] in required]
    missing += [field for field in required if field not in missing]
    return missing, [
        {"field": field, "question": _QUESTION_BY_MISSING_FIELD[field]} for field in missing
    ]


def _declares_missing(statuses: list[str]) -> bool:
    """Whether the attachment's one status line is "Attachment status: missing"."""
    return (
        len(statuses) == 1
        and statuses[0][len(_ATTACHMENT_STATUS_LABEL) :].strip().lower() == "missing"
    )


def _receipt_as_declared(intake: Intake, attachment_text: str) -> Intake:
    """The intake, with the receipt absent when the attachment says "Attachment status: missing"."""
    if not _declares_missing(_lines_starting(attachment_text, _ATTACHMENT_STATUS_LABEL)):
        return intake
    declared = intake.copy()
    declared["purchase_receipt"] = _ABSENT
    return declared


def _classification(intake: Intake) -> str | None:
    """Return the supported classification that the intake and statement establish, or None.

    A denied authorization is unauthorized. An absent authorization is the provisional
    unauthorized that asks for confirmation, as the procedure requires; the statement
    does not have to deny the charge. Otherwise an undelivered service is
    service_not_received and two charges for one purchase is duplicate_charge.

    A sentence written as an instruction or a filing command is not read, so "classify
    this as a double charge" in the customer's text cannot choose the class. Ambiguous
    and unsupported complaints are escalated before this point, so anything else is
    None: the rules found no type.
    """
    if intake["authorization"] in (_DENIED, _ABSENT):
        return "unauthorized"
    sentences = _account_sentences(intake["statement"])
    if any(_SERVICE.search(sentence) for sentence in sentences):
        return "service_not_received"
    if any(
        _DUPLICATE.search(sentence) and not _NOT_DUPLICATE.search(sentence)
        for sentence in sentences
    ):
        return "duplicate_charge"
    return None


def _model_lines(statements: Sequence[str], known: Sequence[str]) -> list[StatementLine] | None:
    """The customer lines a model may read, or None when one may not be asked.

    No model is asked about a case whose customer statements hold text the detectors
    recognise as an instruction, a filing command, text addressed to a model or
    evidence-tag markup, so recognised text cannot reach one. Nor is one asked when a
    restricted value would survive redaction (a card number split across two lines, or
    hidden characters between its digits), or when a statement declares no source id to
    cite its lines by. The rules then decide alone, as they do with no model.
    """
    if any(
        has_instruction(text)
        or _is_command(visible(text))
        or addresses_a_model(text)
        for text in statements
    ):
        return None
    try:
        sources = [(_source_id(text), text) for text in statements]
    except ContractError:
        return None
    lines = statement_lines(sources, known)
    # The lines are scanned joined by a space and joined with nothing, so a card number
    # split at any point across a line break is found ("378282" then "246310005").
    shown = [line["shown"] for line in lines]
    if any(restricted_values(visible(joiner.join(shown)), known) for joiner in (" ", "")):
        return None
    return lines


def _model_escalation(
    answer: DisputeType,
    intake: Intake,
    statements: Sequence[str],
    procedure_text: str,
    known: Sequence[str],
) -> Escalation | None:
    """Where a model's answer sends the case, or None when the rules can use its type.

    A cash withdrawal or another kind of dispute is unsupported. "none" leaves the type
    to a person. A denial against a form that confirms authorization, in any letter case,
    is the procedure's conflict about authorization. Each escalation cites the model's
    line exactly, with the procedure sentence it rests on; the model's words are never
    quoted as a rule.
    """
    kind, line = answer["type"], answer["line"]
    procedure_source = _source_id(procedure_text)
    if kind == "none":
        return {"classification": "ambiguous", "reason": _NO_TYPE_REASON, "citations": []}
    if kind == "cash_withdrawal":
        return {
            "classification": "unsupported",
            "reason": (
                "A customer line describes a cash withdrawal, which the procedure does not "
                "support, so no other classification is assigned."
            ),
            "citations": [
                _line_quote("cash_withdrawal", line, statements, known),
                {
                    "claim": "unsupported_rule",
                    "source_id": procedure_source,
                    "quote": _sentence(procedure_text, _UNSUPPORTED_RULE_ANCHOR),
                },
            ],
        }
    if kind == "other_dispute":
        return {
            "classification": "unsupported",
            "reason": (
                "A customer line describes a dispute outside the procedure's supported "
                "classifications, so a person must decide the case."
            ),
            "citations": [
                _line_quote("other_dispute", line, statements, known),
                {
                    "claim": "supported_classifications",
                    "source_id": procedure_source,
                    "quote": _sentence(procedure_text, _SUPPORTED_RULE_ANCHOR),
                },
            ],
        }
    if kind == "unauthorized" and _form_authorization(intake) == _CONFIRMED:
        return {
            "classification": "ambiguous",
            "reason": (
                "The intake form confirms authorization, but a customer line denies it. Both "
                "are cited, and this draft does not decide which statement is correct."
            ),
            "citations": [
                _line_quote("authorization_denied", line, statements, known),
                {
                    "claim": "authorization_confirmed",
                    "source_id": _source_id(statements[0]),
                    "quote": _unique_line(statements[0], _AUTHORIZATION_LABEL),
                },
                {
                    "claim": "ambiguous_rule",
                    "source_id": procedure_source,
                    "quote": _sentence(procedure_text, _AMBIGUOUS_RULE_ANCHOR),
                },
            ],
        }
    return None


def _form_authorization(intake: Intake) -> str:
    """The intake form's authorization answer, compared without letter case or spaces."""
    return intake["authorization"].strip().lower()


def _line_quote(
    claim: str, line: StatementLine, statements: Sequence[str], known: Sequence[str]
) -> Citation:
    """A customer line a model read, quoted exactly from its statement.

    A line that holds a restricted value, a known one included, is cited by its
    statement's Source ID line instead, so the case is drafted and the value is never
    reproduced.
    """
    quote = line["text"]
    if restricted_values(quote, known):
        source = next(text for text in statements if _source_id(text) == line["source_id"])
        quote = _unique_line(source, _SOURCE_ID_LABEL)
    return {"claim": claim, "source_id": line["source_id"], "quote": quote}


def _account_sentences(statement: str) -> list[str]:
    """The statement's sentences that are the customer's account, not instructions."""
    return [
        sentence
        for line in statement.splitlines()
        for sentence in _SENTENCE_END.split(line)
        if not has_instruction(sentence) and not _is_command(sentence)
    ]


def _is_command(text: str) -> bool:
    """True when text holds a filing command that is not negated, or a negated one whose
    own clause names a class.

    "Do not mark this as a duplicate charge" is a command: the cue is inside it. "Please do
    not mark this as resolved, they charged me twice" is not: the cue is a later clause, the
    customer's own account.
    """
    return any(
        not _NEGATED_BEFORE.search(text[: match.start()])
        or _names_a_class(_CLAUSE_END.split(text[match.end() :], maxsplit=1)[0])
        for match in _INSTRUCTION_SENTENCE.finditer(text)
    )


def _names_a_class(text: str) -> bool:
    return bool(_DUPLICATE.search(text) or _SERVICE.search(text))


def _command_holds_cue(texts: Sequence[str]) -> bool:
    """True when a filing command ("classify this as a double charge") holds a dispute cue.

    Such a sentence is not read for its cue, and skipping it must not hide one, so the
    caller sends the case to a person, as it does for text addressed to the system.
    """
    return any(
        _is_command(sentence) and _names_a_class(sentence)
        for text in texts
        for line in text.splitlines()
        for sentence in _SENTENCE_END.split(line)
    )


def _customer_evidence(intake: Intake, intake_text: str, known: Sequence[str]) -> Citation:
    """The customer's own words, quoted exactly; the intake's Source ID line when they hold a
    restricted value (a card number the customer typed, or a value known for the case), so
    the case is drafted, not refused.
    """
    statement = _statement(intake, intake_text)
    if restricted_values(statement, known):
        statement = _unique_line(intake_text, _SOURCE_ID_LABEL)
    return {"claim": "customer_evidence", "source_id": _source_id(intake_text), "quote": statement}


def _other_charge_citations(
    statement: str, transaction_id: str, transactions_text: str
) -> list[Citation]:
    """Cite the second charge of a duplicate, so both transaction records are on file.

    At most one row is cited. It must be the five contract fields and match the named
    charge's merchant, amount and currency. A row the customer names is preferred, and
    naming it stands in for the posting date; any other row must be posted within two
    days of the named charge. Any other row, even one the customer names or one of the
    same amount, is unrelated and is never quoted; a row with extra fields is skipped,
    not fatal.
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
        and all(charge.get(k) == named.get(k) for k in ("merchant_id", "amount", "currency"))
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
    """Posted within two days of the named charge; the caller has already matched the
    merchant, amount and currency.

    A posted date may be a plain date or a full ISO datetime ("2025-03-02T09:00:00"); only
    the calendar day counts. An unreadable date is not the same charge.
    """
    try:
        gap = _posted_day(charge.get("posted_date")) - _posted_day(named.get("posted_date"))
    except ValueError:
        return False
    return abs(gap.days) <= 2


def _posted_day(value: object) -> date:
    return datetime.fromisoformat(str(value)).date()


def _untrusted_notes(record: WorkingRecord, attachment_text: str) -> list[str]:
    """A warning for the reviewer when merchant or attachment text is written as instructions."""
    notes: list[str] = []
    merchant = record.get("merchant")
    if merchant is not None and has_instruction(merchant["note"]):
        notes.append(INSTRUCTION_NOTICE)
    if has_instruction(attachment_text):
        notes.append(ATTACHMENT_INSTRUCTION_NOTICE)
    return notes


def _required_missing(intake: Intake, classification: str) -> list[str]:
    """The required evidence fields that the intake does not supply, in order."""
    return [
        field
        for field in _REQUIRED_MISSING_INFORMATION[classification]
        if _INTAKE_VALUE_BY_MISSING_FIELD[field](intake) == _ABSENT
    ]


def _follow_up_questions(
    intake: Intake, missing_information: list[str]
) -> list[FollowUpQuestion]:
    """One targeted question per missing field, in the order the record lists them.

    A field the intake already supplies is refused rather than questioned, and an
    identifier outside the contract's allowed set is refused rather than guessed.
    """
    questions: list[FollowUpQuestion] = []
    for identifier in missing_information:
        value = _INTAKE_VALUE_BY_MISSING_FIELD.get(identifier)
        if value is None:
            raise ContractError(f"unknown missing information identifier {identifier!r}")
        if value(intake) != _ABSENT:
            raise ContractError(
                f"{identifier} is listed as missing but the intake supplies it"
            )
        questions.append(
            {"field": identifier, "question": _QUESTION_BY_MISSING_FIELD[identifier]}
        )
    return questions


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


def _transaction_citations(
    transaction_id: str, transactions_text: str | None, procedure_text: str
) -> list[Citation]:
    """The named charge from the tool body, or, when the service stayed unavailable, the
    procedure sentences that say to stop retrying and leave amount and currency null.

    No transactions source is cited for an unavailable service, because none was read.
    """
    if transactions_text is not None:
        return [_transaction_citation(transaction_id, transactions_text)]
    procedure_source = _source_id(procedure_text)
    return [
        {
            "claim": "transaction_service_unavailable",
            "source_id": procedure_source,
            "quote": _sentence(procedure_text, anchor),
        }
        for anchor in (_RETRY_RULE_ANCHOR, _UNAVAILABLE_FACTS_ANCHOR)
    ]


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
    """Return the deadline and the per-type policy line it is calculated from."""
    quote = _unique_line(policy_text, _DEADLINE_LABEL[classification])
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
