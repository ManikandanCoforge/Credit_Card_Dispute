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
from collections.abc import Iterable

# Text written as an order to whoever reads it, rather than as a statement of fact.
_INSTRUCTION = re.compile(
    r"\bsystem override\b"
    r"|\bignore (?:all |the |any )?(?:bank |previous |prior |above )?"
    r"(?:policy|policies|instructions?|rules?)\b"
    r"|\bpromise (?:an? |the )?(?:immediate |full )?refund\b"
    r"|\bskip (?:the )?(?:human )?approval\b"
    r"|\bcopy (?:all |the |any )?(?:private )?tokens?\b"
    r"|\b(?:administrator|admin|developer) (?:priority|mode|override)\b"
    r"|\bmark (?:this|the case|it) (?:as )?(?:ready|resolved|approved)\b",
    re.IGNORECASE,
)
_RESTRICTED = re.compile(
    r"SYNTHETIC-PRIVATE-[A-Z0-9-]+"  # synthetic private token
    r"|\bCUST-[A-Z0-9-]+"  # customer reference, treated as an account number
    r"|(?<![\d-])(?:\d{4}[ -]){3}\d{1,7}(?![\d-])"  # a card number in groups of four
    r"|(?<!\d)\d{13,19}(?!\d)"  # a card number written without spaces
)

INSTRUCTION_NOTICE = (
    "The merchant record contains text written as instructions. It was treated as "
    "evidence only and was not followed or reproduced."
)


class RestrictedValueError(Exception):
    """A restricted value was about to leave the application."""


def has_instruction(text: str) -> bool:
    """True when the text contains an instruction addressed to the system."""
    return _INSTRUCTION.search(text) is not None


def restricted_values(value: object, known: Iterable[str] = ()) -> list[str]:
    """Every restricted value in the JSON form of value, in order of appearance.

    known adds exact values, such as the private token a tool body carried, so a
    token that does not follow the usual pattern is still found.
    """
    emitted = json.dumps(value, ensure_ascii=False)
    found = [match.group(0) for match in _RESTRICTED.finditer(emitted)]
    found += [secret for secret in known if secret and secret in emitted]
    return list(dict.fromkeys(found))


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
