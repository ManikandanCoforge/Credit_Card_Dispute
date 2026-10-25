"""Find the complaints the procedure sends to a human before any classification.

Two rules in CARD-PROCEDURE-01 escalate a complaint:

  Cash withdrawal disputes are unsupported; classification is unsupported and deadline is null.
  If customer accounts conflict about authorization, classification is ambiguous; deadline is null.

Only customer statements are read: the intake and any document whose heading
marks it as customer correspondence. An attachment or a merchant note never
decides escalation, so a planted "Authorization:" line in a receipt is ignored.

unsupported is checked first. Both routes are manual_review with a null
deadline, so the order only decides which class is reported.
"""

import re
from typing import TypedDict

_UNSUPPORTED_RULE_ANCHOR = "Cash withdrawal disputes are unsupported"
_AMBIGUOUS_RULE_ANCHOR = "If customer accounts conflict about authorization"
_SOURCE_ID_LABEL = "Source ID:"
_AUTHORIZATION_LABEL = "Authorization:"

# A cash withdrawal, however the customer words it.
_CASH = re.compile(
    r"\bATM\b|\bcash (?:machine|withdrawal)s?\b|\bwithdr[ae]w\w*\b[^.!?]*\bcash\b"
    r"|\bcash\b[^.!?]*\bwithdr[ae]w\w*|\bdispens\w*",
    re.IGNORECASE,
)
# The customer's own account of authorization, in prose.
_DENIES = re.compile(
    r"\b(?:do not|don't|did not|didn't) recogni[sz]e\b"
    r"|\b(?:did not|didn't|never) authori[sz]e"
    r"|\bnot authori[sz]ed by me\b",
    re.IGNORECASE,
)
_CONFIRMS = re.compile(
    r"\bI (?:did |do )?authori[sz]ed?\b|\bI made (?:this|the) purchase\b",
    re.IGNORECASE,
)
# A form line such as "Transaction ID: TX-D01". Only the Authorization line is read.
_LABEL_LINE = re.compile(r"[A-Z][A-Za-z ]*:")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class Quote(TypedDict):
    claim: str
    source_id: str
    quote: str


class Escalation(TypedDict):
    classification: str
    reason: str
    citations: list[Quote]


class EscalationError(Exception):
    """A statement or rule needed to escalate cannot be quoted from its source."""


def find_escalation(
    intake_text: str, customer_texts: list[str], procedure_text: str
) -> Escalation | None:
    """Return the escalation for this complaint, or None when the procedure gives none.

    Every returned citation is an exact single-line excerpt of its source.
    """
    cash = _cash_sentence(intake_text)
    if cash is not None:
        return {
            "classification": "unsupported",
            "reason": (
                "The complaint describes a cash withdrawal, which the procedure does not "
                "support, so no other classification is assigned."
            ),
            "citations": [
                {"claim": "cash_withdrawal", "source_id": _source_id(intake_text), "quote": cash},
                _rule(procedure_text, _UNSUPPORTED_RULE_ANCHOR, "unsupported_rule"),
            ],
        }
    denials: list[Quote] = []
    confirmations: list[Quote] = []
    for text in [intake_text, *customer_texts]:
        denied, confirmed = _stances(text)
        if denied is not None:
            denials.append(
                {"claim": "authorization_denied", "source_id": _source_id(text), "quote": denied}
            )
        if confirmed is not None:
            confirmations.append(
                {
                    "claim": "authorization_confirmed",
                    "source_id": _source_id(text),
                    "quote": confirmed,
                }
            )
    if not denials or not confirmations:
        return None
    deny_ids = _joined(denials)
    confirm_ids = _joined(confirmations)
    return {
        "classification": "ambiguous",
        "reason": (
            "Customer statements conflict about authorization. "
            f"Denied in {deny_ids}; confirmed in {confirm_ids}. Both sides are cited, and "
            "this draft does not decide which statement is correct."
        ),
        "citations": [
            *denials,
            *confirmations,
            _rule(procedure_text, _AMBIGUOUS_RULE_ANCHOR, "ambiguous_rule"),
        ],
    }


def _cash_sentence(intake_text: str) -> str | None:
    """The first prose sentence of the intake that describes a cash withdrawal."""
    for sentence in _prose_sentences(intake_text):
        if _CASH.search(sentence):
            return sentence
    return None


def _stances(text: str) -> tuple[str | None, str | None]:
    """The first quote that denies and the first that confirms authorization, if any."""
    denied: str | None = None
    confirmed: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(_AUTHORIZATION_LABEL):
            value = line[len(_AUTHORIZATION_LABEL) :].strip().lower()
            if value == "denied" and denied is None:
                denied = line
            if value == "confirmed" and confirmed is None:
                confirmed = line
            continue
        for sentence in _sentences(line):
            if _DENIES.search(sentence) and denied is None:
                denied = sentence
            elif _CONFIRMS.search(sentence) and confirmed is None:
                confirmed = sentence
    return denied, confirmed


def _prose_sentences(text: str) -> list[str]:
    return [sentence for line in text.splitlines() for sentence in _sentences(line.strip())]


def _sentences(line: str) -> list[str]:
    """The sentences of one prose line. Headings and form lines have none."""
    if not line or line.startswith("#") or _LABEL_LINE.match(line):
        return []
    return [sentence for sentence in _SENTENCE_END.split(line) if sentence]


def _rule(procedure_text: str, anchor: str, claim: str) -> Quote:
    """The procedure sentence that starts at anchor, which must end on its own line."""
    lines = _lines_starting(procedure_text, anchor)
    if len(lines) != 1 or "." not in lines[0]:
        raise EscalationError(f"{anchor!r} is not one sentence in the procedure")
    quote = lines[0][: lines[0].index(".") + 1]
    return {"claim": claim, "source_id": _source_id(procedure_text), "quote": quote}


def _source_id(text: str) -> str:
    lines = _lines_starting(text, _SOURCE_ID_LABEL)
    source_id = lines[0][len(_SOURCE_ID_LABEL) :].strip() if len(lines) == 1 else ""
    if not source_id:
        raise EscalationError("a customer statement or the procedure declares no source id")
    return source_id


def _lines_starting(text: str, start: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith(start)]


def _joined(quotes: list[Quote]) -> str:
    return " and ".join(dict.fromkeys(quote["source_id"] for quote in quotes))
