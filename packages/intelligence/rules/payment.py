"""Payment phrases: advance, on or after delivery, net days, instalments, vague "later" (AI_SPEC section 3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from packages.intelligence.normalize import nfc, normalize

from .base import NOT_AFTER, NOT_BEFORE, Match

Kind = Literal["net_days", "on_delivery", "after_delivery", "on_completion", "instalments", "advance", "later"]
# Listed in priority order: when two phrases overlap, the earlier kind wins ("30 days after delivery").
_PATTERNS: list[tuple[Kind, str]] = [
    ("net_days", rf"(?P<d>\d{{1,3}})\s*(?:days?|din)\s*(?:(?:of|after|from)\s+(?:the\s+)?(?:delivery|completion|invoice|receipt)|(?:ke\s+)?baad|ke\s+andar)"),
    ("net_days", r"net\s*(?P<d>\d{1,3})"),
    ("on_delivery", rf"(?:cash\s+)?(?:on|at)\s+delivery|delivery\s+(?:par|pe|pr)|cod|{nfc('डिलीवरी')}\s+(?:पर|पे)"),
    ("after_delivery", rf"after\s+(?:the\s+)?delivery|post[- ]delivery|delivery\s+ke\s+baad|{nfc('डिलीवरी')}\s+के\s+बाद"),
    ("on_completion", rf"(?:on|after)\s+completion|on\s+completing|when\s+(?:the\s+)?work\s+is\s+(?:done|complete)|{nfc('काम')}\s+{nfc('पूरा')}"),
    ("instalments", rf"(?:(?P<n>\d+)\s+)?(?:instal+ments?|emi|kist|kisht|milestones?|{nfc('किस्त')})"),
    ("advance", rf"advance|peshgi|up\s*front|{nfc('एडवांस')}"),
    ("later", rf"later|soon|baad\s+m(?:ein|e|ain)|baadmein|when\s+i\s+can|jab\s+ho\s+sake|{nfc('बाद में')}|{nfc('जब हो सके')}"),
]
_COMPILED = [(kind, re.compile(rf"{NOT_AFTER}(?:{p}){NOT_BEFORE}", re.IGNORECASE)) for kind, p in _PATTERNS]


@dataclass(frozen=True, kw_only=True)
class PaymentMatch(Match):
    kind: Kind
    days: int | None = None
    vague: bool = False


def parse_payment_phrases(text: str) -> list[PaymentMatch]:
    nz = normalize(text)
    found: list[PaymentMatch] = []
    taken: list[tuple[int, int]] = []
    for kind, pattern in _COMPILED:
        for m in pattern.finditer(nz.text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            days = int(m["d"]) if "d" in pattern.groupindex and m["d"] else None
            found.append(PaymentMatch(**nz.locate(m.start(), m.end()), kind=kind, days=days, vague=kind == "later"))
    return sorted(found, key=lambda p: p.start)
