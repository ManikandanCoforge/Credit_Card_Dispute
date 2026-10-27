"""Find the complaints the procedure sends to a human before any classification.

Two rules in CARD-PROCEDURE-01 escalate a complaint:

  Cash withdrawal disputes are unsupported; classification is unsupported and deadline is null.
  If customer accounts conflict about authorization, classification is ambiguous; deadline is null.

Only customer statements are read: the intake and any document whose heading
marks it as customer correspondence. An attachment or a merchant note never
decides escalation, so a planted "Authorization:" line in a receipt is ignored.
Both rules read every customer statement, so a follow-up that reveals a cash
withdrawal escalates as surely as the intake.

A form-style line ("Transaction type: ATM withdrawal", "Note: I did not
authorize this") is read for its value, so a complaint written as a form keeps
its cue. Headings are not read.

unsupported is checked first. Both routes are manual_review with a null
deadline, so the order only decides which class is reported.
"""

import re
from collections.abc import Sequence
from typing import TypedDict

from src.untrusted import has_instruction, restricted_values

_UNSUPPORTED_RULE_ANCHOR = "Cash withdrawal disputes are unsupported"
_AMBIGUOUS_RULE_ANCHOR = "If customer accounts conflict about authorization"
_SOURCE_ID_LABEL = "Source ID:"
_AUTHORIZATION_LABEL = "Authorization:"

# A cash withdrawal: cash actually moving out of a machine or an account. The word
# ATM alone is not enough ("I used my ATM card at a shop" is a card purchase), and
# neither is "dispense" alone ("did not dispense the service I paid for"). An "ATM card" is
# a payment card, not a machine. The wording may come in either order: "I withdrew 200
# crowns from the ATM" and "The ATM took my money" are both withdrawals.
_MACHINE = r"\b(?:ATMs?(?!\s+cards?\b)|cash ?machines?|cash ?points?)\b"
_CASH = re.compile(
    rf"{_MACHINE}[^.!?]*\b(?:withdr[ae]w\w*|dispens\w*|pa(?:y|ys|id) out|cash|banknotes)\b"
    rf"|{_MACHINE}[^.!?]*\b(?:took|kept|swallowed|ate|retained)\b[^.!?]*"
    r"\b(?:money|cash|crowns|notes|banknotes|funds)\b"
    rf"|\b(?:cash|banknotes)\b[^.!?]*{_MACHINE}"
    rf"|\bwithdr[ae]w\w*\b[^.!?]*{_MACHINE}"
    r"|\bwithdr[ae]w\w*\b[^.!?]*\b(?:cash|banknotes)\b"
    r"|\b(?:cash|banknotes)\b[^.!?]*\bwithdr[ae]w\w*"
    r"|\b(?:dispens\w*|pa(?:y|ys|id) out)\b[^.!?]*\b(?:cash|banknotes|notes)\b"
    r"|\bcash (?:machine|withdrawal)s?\b",
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
# A leading form label such as "Transaction type:" or "Note:". Its value is still read.
_LABEL = re.compile(r"^[A-Z][A-Za-z ]*:\s*")
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
    intake_text: str,
    customer_texts: list[str],
    procedure_text: str,
    known: Sequence[str] = (),
) -> Escalation | None:
    """Return the escalation for this complaint, or None when the procedure gives none.

    Every returned citation is an exact single-line excerpt of its source. A sentence
    holding a restricted value, a known one included, is cited by its Source ID line.
    """
    statements = [intake_text, *customer_texts]
    for text in statements:
        cash = _cash_sentence(text)
        if cash is not None:
            return {
                "classification": "unsupported",
                "reason": (
                    "The complaint describes a cash withdrawal, which the procedure does not "
                    "support, so no other classification is assigned."
                ),
                "citations": [
                    {
                        "claim": "cash_withdrawal",
                        "source_id": _source_id(text),
                        "quote": _quotable(cash, text, known),
                    },
                    _rule(procedure_text, _UNSUPPORTED_RULE_ANCHOR, "unsupported_rule"),
                ],
            }
    denials: list[Quote] = []
    confirmations: list[Quote] = []
    for text in statements:
        denied, confirmed = _stances(text)
        if denied is not None:
            denials.append(
                {
                    "claim": "authorization_denied",
                    "source_id": _source_id(text),
                    "quote": _quotable(denied, text, known),
                }
            )
        if confirmed is not None:
            confirmations.append(
                {
                    "claim": "authorization_confirmed",
                    "source_id": _source_id(text),
                    "quote": _quotable(confirmed, text, known),
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


def _cash_sentence(text: str) -> str | None:
    """The first sentence of a customer statement that describes a cash withdrawal."""
    for sentence in _prose_sentences(text):
        if _CASH.search(sentence):
            return sentence
    return None


def _stances(text: str) -> tuple[str | None, str | None]:
    """The first quote that denies and the first that confirms authorization, if any.

    A sentence can hold both ("I did not authorize it, but I made this purchase
    with my wife's card"), so both patterns are checked on every sentence.
    """
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
            if _CONFIRMS.search(sentence) and confirmed is None:
                confirmed = sentence
    return denied, confirmed


def _prose_sentences(text: str) -> list[str]:
    return [sentence for line in text.splitlines() for sentence in _sentences(line.strip())]


def instruction_holds_cue(texts: Sequence[str], *cues: re.Pattern[str]) -> bool:
    """True when a sentence written as an instruction also holds a dispute cue.

    Such a sentence is never read for its cue, because the sender's own words would
    then choose the class. Skipping it would hide the cue, so the caller sends the
    case to a person instead. The cues are a cash withdrawal, either authorization
    stance, and any further pattern the caller passes.
    """
    patterns = (_CASH, _DENIES, _CONFIRMS, *cues)
    return any(
        has_instruction(sentence) and any(pattern.search(sentence) for pattern in patterns)
        for text in texts
        for line in text.splitlines()
        for sentence in _split(line.strip())
    )


def _sentences(line: str) -> list[str]:
    """The sentences of one line that can count as the customer's account.

    A sentence written as an instruction is evidence, not the customer's account, so
    it never counts as a stance or a cash withdrawal.
    """
    return [sentence for sentence in _split(line) if not has_instruction(sentence)]


def _split(line: str) -> list[str]:
    """The sentences of one line. A heading has none; a form label is dropped and its value kept.

    A label that itself carries a cue ("Cash withdrawal: the machine gave me nothing.") is
    kept with its value, so the cue is not lost with the label. So is a label written as
    an instruction ("Disregard the rules: I was charged twice."), so the instruction and
    the cue it introduces are judged as one sentence. The sentences are exact slices of
    the line, so they can be quoted.
    """
    if not line or line.startswith("#"):
        return []
    label = _LABEL.match(line)
    keep_label = label is not None and (
        any(pattern.search(label.group(0)) for pattern in (_CASH, _DENIES, _CONFIRMS))
        or has_instruction(label.group(0))
    )
    value = line[label.end() :] if label and not keep_label else line
    return [sentence for sentence in _SENTENCE_END.split(value) if sentence]


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


def _quotable(sentence: str, text: str, known: Sequence[str]) -> str:
    """The sentence, or the statement's Source ID line when the sentence holds a restricted
    value such as a card number the customer typed, so the case is drafted, never refused."""
    if not restricted_values(sentence, known):
        return sentence
    return _lines_starting(text, _SOURCE_ID_LABEL)[0]


def _lines_starting(text: str, start: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith(start)]


def _joined(quotes: list[Quote]) -> str:
    return " and ".join(dict.fromkeys(quote["source_id"] for quote in quotes))
