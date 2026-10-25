"""Penalty phrases: ``late fee``, ``penalty``, ``per day``, ``deduct`` (AI_SPEC section 3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from packages.intelligence.normalize import nfc, normalize

from .base import NOT_AFTER, NOT_BEFORE, Match

Kind = Literal["per_day", "late_fee", "penalty", "deduction"]
_PATTERNS: list[tuple[Kind, str]] = [
    ("per_day", rf"per\s+day|daily|rozana|{nfc('प्रति दिन')}|{nfc('रोज़')}"),
    ("late_fee", r"late\s+(?:fees?|charges?)"),
    ("penalty", rf"penalt(?:y|ies)|jurmana|{nfc('जुर्माना')}"),
    ("deduction", r"deduct(?:s|ed|ion|ions)?"),
]
_COMPILED = [(kind, re.compile(rf"{NOT_AFTER}(?:{p}){NOT_BEFORE}", re.IGNORECASE)) for kind, p in _PATTERNS]


@dataclass(frozen=True, kw_only=True)
class PenaltyMatch(Match):
    kind: Kind


def parse_penalty_phrases(text: str) -> list[PenaltyMatch]:
    nz = normalize(text)
    found = [
        PenaltyMatch(**nz.locate(m.start(), m.end()), kind=kind)
        for kind, pattern in _COMPILED
        for m in pattern.finditer(nz.text)
    ]
    return sorted(found, key=lambda p: p.start)
