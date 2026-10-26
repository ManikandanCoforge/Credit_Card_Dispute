"""Untrusted evidence and restricted values.

Merchant text, attachments and customer prose are evidence, never instructions.
CARD-PROCEDURE-01: "merchant text is untrusted evidence and cannot change
instructions or rules." Nothing here decides a classification, a route or a
deadline. It only tells the draft that instruction-like text was present, so a
reviewer is warned, and keeps restricted values out of anything we emit.

Restricted values: "Customer account numbers and synthetic private tokens are
unnecessary in summaries or logs; do not reproduce them." Card numbers are
treated the same way.
"""

import json
import re
import unicodedata
from collections.abc import Iterable, Iterator

# Zero-width and bidi control characters an attacker can hide inside a word.
_INVISIBLE = dict.fromkeys(
    [0x00AD, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]
)
# Text written as an order to whoever reads it, rather than as a statement of fact.
# Words may be separated by any run of whitespace, including a line break.
_INSTRUCTION = re.compile(
    r"\bsystem\s+override\b"
    r"|\bignore\s+(?:(?:all|the|any)\s+)?(?:(?:bank|previous|prior|above)\s+)?"
    r"(?:policy|policies|instructions?|rules?)\b"
    r"|\bpromise\s+(?:(?:an?|the)\s+)?(?:(?:immediate|full)\s+)?refund\b"
    r"|\bskip\s+(?:the\s+)?(?:human\s+)?approval\b"
    r"|\bcopy\s+(?:(?:all|the|any)\s+)?(?:private\s+)?tokens?\b"
    r"|\b(?:administrator|admin|developer)\s+(?:priority|mode|override)\b"
    r"|\bmark\s+(?:this|the\s+case|it)\s+(?:as\s+)?(?:ready|resolved|approved)\b",
    re.IGNORECASE,
)
# "Do not ignore policy" and "please do not mark this as resolved" are not orders to do so.
_NEGATED = re.compile(r"\b(?:do\s+not|don't|dont|never|not)\s+$", re.IGNORECASE)
# Text that speaks to a model reading the evidence, or markup that would open or close the
# evidence block a model is shown (ADR-003). These are the Card Disputes Copilot's patterns for
# text addressed to a model, which _INSTRUCTION does not cover.
_TO_A_MODEL = re.compile(
    r"^\s*(?:(?:dear|hey|hi|hello)\s+)?(?:assistant|ai|model|bot|chatbot)\s*[,:]"
    r"|\bnote\s+to\s+(?:the\s+)?(?:assistant|ai|model)\b"
    r"|\bapprove\s+(?:this|it|now)\b"
    r"|\bclassify\s+(?:this|it)\s+as\b"
    r"|</?\s*evidence\b",
    re.IGNORECASE | re.MULTILINE,
)
_TOKENS = re.compile(
    r"SYNTHETIC-PRIVATE-[A-Za-z0-9-]+"  # synthetic private token
    r"|\bCUST-[A-Za-z0-9-]+"  # customer reference, treated as an account number
)
# 15 to 19 plain digits, or a card grouping with one consistent separator (a run of
# whitespace, a dot or a dash, the same each time): 4-4-4-4(-3) or Amex 4-6-5. Two dates
# side by side are not a grouping. A card only when the Luhn check also passes. Plain
# digits start at 15 (Amex) so a 13-digit millisecond timestamp or reference that happens
# to pass Luhn is not a card; a grouped 13-digit card is still caught.
_CARD_LIKE = re.compile(
    r"(?<![\w-])(?<!\d\.)(?:\d{15,19}"
    r"|\d{4}(?P<s>\s+|[.-])\d{4}(?P=s)\d{4}(?P=s)\d{1,7}"
    r"|\d{4}(?P<a>\s+|[.-])\d{6}(?P=a)\d{5})(?![\w-])(?!\.\d)"
)

INSTRUCTION_NOTICE = (
    "The merchant record contains text written as instructions. It was treated as "
    "evidence only and was not followed or reproduced."
)
# What a restricted value becomes in text that leaves the application, such as a model prompt.
REDACTED = "[redacted]"


class RestrictedValueError(Exception):
    """A restricted value was about to leave the application."""


def has_instruction(text: str) -> bool:
    """True when the text contains an instruction addressed to the system.

    The text is normalized first (NFKC, hidden characters removed), so
    "ig<zero-width>nore policy" or "Ignore  policy" is still caught. A negated
    form ("do not ignore policy") is not an instruction.
    """
    probe = visible(text)
    return any(
        not _NEGATED.search(probe[: match.start()]) for match in _INSTRUCTION.finditer(probe)
    )


def addresses_a_model(text: str) -> bool:
    """True when the text speaks to a model ("Hi AI: ...", "note to the assistant",
    "approve this", "classify it as") or carries markup that opens or closes the
    evidence block a model is shown.

    The text is normalized as has_instruction normalizes it, and a negated form ("I did
    not approve this charge") does not count. A model is never asked about a statement
    that holds such text; see src/contract.py.
    """
    probe = visible(text)
    return any(
        not _NEGATED.search(probe[: match.start()]) for match in _TO_A_MODEL.finditer(probe)
    )


def visible(text: str) -> str:
    """text as instructions and values are detected in: NFKC, with hidden characters removed.

    It is never quoted; quotes are copied from the original text.
    """
    return unicodedata.normalize("NFKC", text).translate(_INVISIBLE)


def restricted_values(value: object, known: Iterable[str] = ()) -> list[str]:
    """Every restricted value in value, in order of appearance.

    Strings and numbers are scanned, so a card carried as an integer is caught too.
    A timestamp in seconds or milliseconds has at most 13 digits and is never a card;
    write finer timestamps as text or seconds. known adds exact values, such as the
    private token a tool body carried; each is matched as a whole word, so "1234" is
    not found inside "12346".
    """
    found: list[str] = []
    secrets = [secret for secret in known if secret]
    # Each string is also scanned in its visible form, so a card number broken up by
    # zero-width characters, or typed in full-width digits, is still found.
    for text in dict.fromkeys(form for raw in _strings(value) for form in (raw, visible(raw))):
        found += [match.group(0) for match in _TOKENS.finditer(text)]
        found += [
            card.group(0)
            for card in _CARD_LIKE.finditer(text)
            if _luhn(re.sub(r"\D", "", card.group(0)))
        ]
        found += [
            secret
            for secret in secrets
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])", text)
        ]
    return list(dict.fromkeys(found))


def redact(text: str, known: Iterable[str] = ()) -> str:
    """text with every restricted value replaced by [redacted].

    A model may read a customer's own lines, never the values in them. Longer values
    are replaced first, so a token is never left half visible inside a longer one.
    """
    for value in sorted(restricted_values(text, known), key=len, reverse=True):
        text = text.replace(value, REDACTED)
    return text


def guard(value: object, known: Iterable[str] = ()) -> None:
    """Raise RestrictedValueError when value holds a restricted value.

    The error never repeats the value it found.
    """
    if restricted_values(value, known):
        raise RestrictedValueError("a restricted value was about to be emitted")


def safe_line(event: dict[str, object], known: Iterable[str] = ()) -> str:
    """One JSON log or meter line, refused when it would carry a restricted value."""
    guard(event, known)
    return json.dumps(event, sort_keys=True)


def _strings(value: object) -> Iterator[str]:
    """Every string in a JSON-shaped value: dict keys and values, list items, scalars.

    Integers and floats are yielded in their text form; booleans are not numbers here.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, int | float) and not isinstance(value, bool):
        yield str(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _strings(item)


def _luhn(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        number = int(char) * (2 if position % 2 else 1)
        total += number - 9 if number > 9 else number
    return total % 10 == 0
