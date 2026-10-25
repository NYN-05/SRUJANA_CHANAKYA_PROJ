"""Date parser: absolute, numeric with the deal's date order, relative and partial dates (FR-EXT-003).

Rule ids match the playbook ambiguity rules: ``rel_date``, ``partial_date``, ``order_date``.
A month and day with no year take the next occurrence on or after ``reference`` (no flag).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from packages.intelligence.normalize import nfc, normalize

from .base import NOT_AFTER, NOT_BEFORE, Match, alternation

MONTHS: dict[str, int] = {}
for _n, _names in enumerate(
    [
        "january jan जनवरी",
        "february feb फरवरी फ़रवरी",
        "march mar मार्च",
        "april apr अप्रैल",
        "may मई",
        "june jun जून",
        "july jul जुलाई",
        "august aug अगस्त",
        "september sept sep सितंबर सितम्बर",
        "october oct अक्टूबर अक्तूबर",
        "november nov नवंबर नवम्बर",
        "december dec दिसंबर दिसम्बर",
    ],
    start=1,
):
    for _name in _names.split():
        MONTHS[nfc(_name)] = _n

MONTH_RE = alternation(list(MONTHS))
_YEAR = r"(?:19|20)\d{2}"
_ORD = r"(?:st|nd|rd|th)"
_PATTERNS = {
    "dmy_name": rf"{NOT_AFTER}(?P<d>\d{{1,2}}){_ORD}?\s*(?:of\s+)?(?P<mon>{MONTH_RE}){NOT_BEFORE}\.?(?:,?\s*(?P<y>{_YEAR})(?!\d))?",
    "mdy_name": rf"{NOT_AFTER}(?P<mon>{MONTH_RE}){NOT_BEFORE}\.?\s*(?P<d>\d{{1,2}})(?!\d){_ORD}?(?:,?\s*(?P<y>{_YEAR})(?!\d))?",
    "numeric": rf"{NOT_AFTER}(?P<a>\d{{1,2}})(?P<sep>[/.\-])(?P<b>\d{{1,2}})(?P=sep)(?P<y>\d{{4}}|\d{{2}})(?!\d)(?![/.\-]\d)",
    "iso": rf"{NOT_AFTER}(?P<y>{_YEAR})-(?P<m>\d{{2}})-(?P<d>\d{{2}})(?!\d)",
    "ordinal": rf"{NOT_AFTER}(?P<d>\d{{1,2}})(?:{_ORD}{NOT_BEFORE}|\s*(?:tarikh|tareekh|{nfc('तारीख')}|{nfc('तारिख')}){NOT_BEFORE})",
    "relative": rf"{NOT_AFTER}(?:(?:next|this|coming)\s+(?:week|month)|end\s+of\s+(?:the\s+)?(?:week|month)|as\s+soon\s+as\s+possible|"
    rf"agle\s+hafte|is\s+hafte|{nfc('अगले हफ्ते')}|soon|asap|tomorrow|kal|parso|jaldi|jald|{nfc('कल')}|{nfc('परसों')}|{nfc('जल्दी')}){NOT_BEFORE}",
}
_COMPILED = {name: re.compile(p, re.IGNORECASE) for name, p in _PATTERNS.items()}


@dataclass(frozen=True, kw_only=True)
class DateMatch(Match):
    kind: Literal["absolute", "ambiguous_order", "relative", "partial"]
    value: date | None
    readings: tuple[date, ...] = ()
    rule_id: str | None = None


def _make(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _next_occurrence(m: int, d: int, reference: date) -> date | None:
    for year in range(reference.year, reference.year + 5):  # also finds the next 29 Feb
        found = _make(year, m, d)
        if found and found >= reference:
            return found
    return None


def _candidate(name: str, g: re.Match[str], reference: date, order: str | None) -> tuple[str, date | None, tuple[date, ...]] | None:
    """(kind, value, readings) for one regex match, or None when it is not a real date."""
    if name in ("dmy_name", "mdy_name"):
        month, day = MONTHS[nfc(g["mon"].lower())], int(g["d"])
        found = _make(int(g["y"]), month, day) if g["y"] else _next_occurrence(month, day, reference)
        return ("absolute", found, ()) if found else None
    if name == "iso":
        found = _make(int(g["y"]), int(g["m"]), int(g["d"]))
        return ("absolute", found, ()) if found else None
    if name == "numeric":
        year = int(g["y"]) + (2000 if len(g["y"]) == 2 else 0)
        a, b = int(g["a"]), int(g["b"])
        readings = {"DMY": [_make(year, b, a)], "MDY": [_make(year, a, b)]}
        valid = sorted({d for d in (readings[order] if order else readings["DMY"] + readings["MDY"]) if d})
        if not valid:
            return None
        return ("absolute", valid[0], ()) if len(valid) == 1 else ("ambiguous_order", None, tuple(valid))
    if name == "ordinal":
        return ("partial", None, ()) if 1 <= int(g["d"]) <= 31 else None
    return ("relative", None, ())


_RULE = {"ambiguous_order": "order_date", "relative": "rel_date", "partial": "partial_date"}


def parse_dates(text: str, *, reference: date, date_order: str | None) -> list[DateMatch]:
    nz = normalize(text)
    candidates = []
    for name, pattern in _COMPILED.items():
        for g in pattern.finditer(nz.text):
            result = _candidate(name, g, reference, date_order)
            if result:
                candidates.append((g.start(), -(g.end() - g.start()), g.end(), result))
    found: list[DateMatch] = []
    last_end = -1
    for start, _, end, (kind, value, readings) in sorted(candidates, key=lambda c: c[:3]):
        if start < last_end:  # earlier, longer match wins ("15 Nov 2026" over "Nov 20")
            continue
        last_end = end
        found.append(DateMatch(**nz.locate(start, end), kind=kind, value=value, readings=readings, rule_id=_RULE.get(kind)))
    return found
