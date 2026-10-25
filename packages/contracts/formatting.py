"""Money and date text shared by every package (PHASES.md I-17). Pure functions, no I/O."""

from __future__ import annotations

from datetime import date

_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}


def format_inr(paise: int | str) -> str:
    """``9600000`` becomes ``₹96,000``; Indian grouping; paise shown only when not zero (``₹1,234.50``)."""
    if isinstance(paise, str):
        if not (paise.isascii() and paise.isdigit()):
            raise ValueError(f"paise must be a non-negative whole number, not {paise!r}")
        paise = int(paise)
    if isinstance(paise, bool) or not isinstance(paise, int) or paise < 0:
        raise ValueError(f"paise must be a non-negative whole number, not {paise!r}")
    rupees, cents = divmod(paise, 100)
    digits = str(rupees)
    grouped = digits if len(digits) <= 3 else _group(digits[:-3]) + "," + digits[-3:]
    return f"₹{grouped}" + (f".{cents:02d}" if cents else "")


def _group(head: str) -> str:
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts)


def format_date(value: date | str, lang: str) -> str:
    """``15 Nov 2026`` in English, ``15 नवंबर 2026`` in Hindi. Accepts a date or ``YYYY-MM-DD`` text."""
    if lang not in _MONTHS:
        raise ValueError(f"unknown language {lang!r}")
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return f"{value.day} {_MONTHS[lang][value.month - 1]} {value.year}"
