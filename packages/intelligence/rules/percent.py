"""Percentages and shares: ``50%``, ``half``, ``aadha`` (AI_SPEC section 3). Values are basis points."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from packages.intelligence.normalize import nfc, normalize

from .base import NOT_AFTER, NOT_BEFORE, Match

_PERCENT = re.compile(
    rf"{NOT_AFTER}(?P<n>\d{{1,3}}(?:\.\d{{1,2}})?)\s*(?:%|percent{NOT_BEFORE}|per\s*cent{NOT_BEFORE}|{nfc('प्रतिशत')}|{nfc('फीसदी')})",
    re.IGNORECASE,
)
_HALF = re.compile(rf"{NOT_AFTER}(?:half|aadha|adha|aadhi|adhi|{nfc('आधा')}|{nfc('आधी')}){NOT_BEFORE}", re.IGNORECASE)


@dataclass(frozen=True, kw_only=True)
class PercentMatch(Match):
    basis_points: int


def parse_percentages(text: str) -> list[PercentMatch]:
    nz = normalize(text)
    found = [
        PercentMatch(**nz.locate(m.start(), m.end()), basis_points=int((Decimal(m["n"]) * 100).to_integral_value(ROUND_HALF_UP)))
        for m in _PERCENT.finditer(nz.text)
    ]
    found += [PercentMatch(**nz.locate(m.start(), m.end()), basis_points=5000) for m in _HALF.finditer(nz.text)]
    return sorted(found, key=lambda p: p.start)
