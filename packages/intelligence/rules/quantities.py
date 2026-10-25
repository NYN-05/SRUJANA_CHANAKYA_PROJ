"""Quantity parser: a number and a unit word, ``dozen``, and vague quantities (AI_SPEC section 3)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from packages.intelligence.normalize import nfc, normalize

from .base import NOT_AFTER, NOT_BEFORE, Match, alternation

BUILTIN_UNITS = (
    "shirts shirt tshirts pcs pc pieces piece kg kgs kilo kilos grams gms bags bag boxes box cartons carton "
    "packets packet sets set items item units unit nos meters metres litres liters bottles cups mugs mug "
    "banners banner posters poster cards pages page hours hrs hour sheets plates copies logos designs "
    "sarees kurtas"
).split()
TIME_WORDS = "days day din hafte hafta weeks week months month mahine hours hour hrs years year".split()
DOZEN = ["dozens", "dozen", "darjan", nfc("दर्जन")]
VAGUE_LEAD = ["some", "a few", "several", "few"]
VAGUE_PHRASES = ["as needed", "zarurat ke hisaab se", "zaroorat ke hisaab se", nfc("जरूरत के हिसाब से")]


@dataclass(frozen=True, kw_only=True)
class QuantityMatch(Match):
    amount: int | None  # None when vague
    unit: str | None
    vague: bool = False


def _unit_re(units: Iterable[str]) -> str:
    return alternation([u.lower() for u in (*BUILTIN_UNITS, *units) if u and u.isascii()] + [nfc(u) for u in units if u and not u.isascii()])


def _compile(units: Iterable[str]) -> tuple[re.Pattern[str], re.Pattern[str]]:
    unit = rf"(?:{_unit_re(units)}){NOT_BEFORE}"
    number = rf"{NOT_AFTER}(?<![/#.,-])(?P<n>\d{{1,3}}(?:,\d{{2,3}})+|\d{{1,9}})(?P<dec>\.\d+)?"
    concrete = re.compile(
        rf"{number}\s*(?:(?P<dz>{alternation(DOZEN)}){NOT_BEFORE}(?:\s+(?P<u>{unit}))?|(?P<u2>{unit}))", re.IGNORECASE
    )
    vague = re.compile(
        rf"{NOT_AFTER}(?:(?:{alternation(VAGUE_LEAD)})\s+(?P<vu>{unit})|(?:{alternation(VAGUE_PHRASES)}){NOT_BEFORE})",
        re.IGNORECASE,
    )
    return concrete, vague


_DEFAULT = _compile(())


def parse_quantities(text: str, *, units: Iterable[str] = ()) -> list[QuantityMatch]:
    """Quantities in ``text``; ``units`` adds playbook unit words to the built-in list."""
    nz = normalize(text)
    concrete, vague = _compile(units) if units else _DEFAULT
    found: list[QuantityMatch] = []
    for m in concrete.finditer(nz.text):
        value = Decimal(m["n"].replace(",", "") + (m["dec"] or ""))
        if value != value.to_integral_value():
            continue
        amount = int(value) * (12 if m["dz"] else 1)
        unit = (m["u"] or m["u2"] or "").lower() or None
        found.append(QuantityMatch(**nz.locate(m.start(), m.end()), amount=amount, unit=unit))
    for m in vague.finditer(nz.text):
        found.append(QuantityMatch(**nz.locate(m.start(), m.end()), amount=None, unit=(m["vu"] or "").lower() or None, vague=True))
    return sorted(found, key=lambda q: q.start)
