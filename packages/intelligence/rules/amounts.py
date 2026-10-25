"""Amount parser: rupees as integer paise (FR-EXT-003; AI_SPEC section 3).

A bare number is money only with a cue: a currency marker, a magnitude word, or a price or payment cue word
next to it. So "200 shirts" is not money and "sent 48000" is. Phone numbers, times, dates and ids never are.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from packages.intelligence.normalize import nfc, normalize

from .base import NOT_AFTER, NOT_BEFORE, NUM_START, Match, alternation
from .dates import MONTH_RE
from .quantities import BUILTIN_UNITS, TIME_WORDS

MAGNITUDES = {
    **{w: 1000 for w in ("k", "thousand", "hazaar", "hazar", "hajar", "हज़ार", "हजार")},
    **{w: 100_000 for w in ("lakh", "lakhs", "lac", "lacs", "लाख")},
    **{w: 10_000_000 for w in ("crore", "crores", "cr", "करोड़", "करोड")},
}
MAGNITUDES = {nfc(k): Decimal(v) for k, v in MAGNITUDES.items()}
NUMBER_WORDS = {
    **{"ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6, "saat": 7, "aath": 8},
    **{"nau": 9, "das": 10, "gyarah": 11, "barah": 12, "pandrah": 15, "solah": 16, "bees": 20, "pachees": 25},
    **{"tees": 30, "chalis": 40, "pachaas": 50, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90},
    **{"sau": 100, "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5},
    **{"एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "दस": 10, "बीस": 20, "तीस": 30, "चालीस": 40},
    **{"पचास": 50, "साठ": 60, "सौ": 100, "डेढ़": 1.5, "ढाई": 2.5},
}
NUMBER_WORDS = {nfc(k): Decimal(str(v)) for k, v in NUMBER_WORDS.items()}
CURRENCIES = {
    **{c: "INR" for c in ("₹", "rs", "inr", "rupee", "rupees", "rupaye", "रुपये", "रु")},
    **{"$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD", "€": "EUR", "eur": "EUR", "euro": "EUR"},
    **{"euros": "EUR", "£": "GBP", "gbp": "GBP", "aed": "AED"},
}
CURRENCIES = {nfc(k): v for k, v in CURRENCIES.items()}
CUES = [
    *("advance", "balance", "total", "price", "rate", "paid", "sent", "fee", "cost", "amount", "payment"),
    *("received", "transferred", "remaining", "baaki", "baki", "bheja", "bhej", "diya", "kul", "keemat", "daam"),
    *(nfc(w) for w in ("एडवांस", "बाकी", "कुल", "भेजा", "दिया", "कीमत", "दाम")),
]
PERIODS = {*TIME_WORDS, "week", "weeks", "weekly", "daily"}

_MAG = rf"(?:{alternation(list(MAGNITUDES))}){NOT_BEFORE}"
_NUM = r"(?:\d{1,3}(?:,\d{2,3})+|\d{1,15})(?:\.\d{1,4})?"
_CUR_WORDS = "rs|inr|usd|eur|gbp|aed|rupees?|rupaye|" + alternation([nfc("रुपये"), nfc("रु")])
_CURP = rf"(?:₹|\$|€|£|(?:{_CUR_WORDS})\.?)"
_CURS = rf"(?:(?:{_CUR_WORDS}|dollars?|euros?)\.?){NOT_BEFORE}"
_END = r"(?![\w:]|/\d|\.\d|\s*%)"
_AMOUNT = re.compile(
    rf"{NUM_START}(?P<tilde>~\s*)?(?:(?P<cp>{_CURP})\s*)?"
    rf"(?:(?P<w>{alternation(list(NUMBER_WORDS))}){NOT_BEFORE}\s+(?P<wm>{_MAG})|(?P<n>{_NUM})(?:\s*(?P<m>{_MAG}))?)"
    rf"(?:\s*(?P<cs>{_CURS}))?(?:\s*/-)?{_END}",
    re.IGNORECASE,
)
_RANGE = re.compile(
    rf"{NUM_START}(?:(?P<cp>{_CURP})\s*)?(?P<a>{_NUM})\s*(?P<ma>{_MAG})?\s*(?:to|-|–|—)\s*(?:(?P<cp2>{_CURP})\s*)?"
    rf"(?P<b>{_NUM})(?:\s*(?P<mb>{_MAG}))?(?:\s*(?P<cs>{_CURS}))?{_END}",
    re.IGNORECASE,
)
_BOUNDARY = re.compile(r"[,;!?]|\.(?=\s|$)")
_BEFORE = re.compile(rf"(?:{NOT_AFTER}(?P<c>{alternation(CUES)}){NOT_BEFORE}(?:\s+[^\W\d_]+)?|(?P<at>@))\s*[:=]?\s*$", re.IGNORECASE)
_AFTER = re.compile(r"\s*(?:(?P<each>each|ea)(?![A-Za-z])|per\s+(?P<pu>[a-z]+)|/\s*(?P<su>[a-z]+)(?![A-Za-z])|(?P<total>total)(?![A-Za-z]))", re.IGNORECASE)
_APPROX = re.compile(rf"{NOT_AFTER}(?:approx\.?|approximately|around|about|roughly|nearly|lagbhag|{nfc('लगभग')})\s*$", re.IGNORECASE)


@dataclass(frozen=True, kw_only=True)
class AmountMatch(Match):
    paise: int | None  # None for a range
    currency: str = "INR"
    per: Literal["item", "total"] | None = None
    approximate: bool = False
    is_range: bool = False
    low_paise: int | None = None
    high_paise: int | None = None
    cue: str | None = None  # the price or payment cue word that made it money, if any
    period: str | None = None  # "day", "week", ... for "500 per day"


def _paise(number: str, magnitude: str | None) -> int:
    value = Decimal(number.replace(",", "")) * (MAGNITUDES.get(nfc(magnitude.lower()), Decimal(1)) if magnitude else 1)
    return int((value * 100).to_integral_value(ROUND_HALF_UP))


def _currency(token: str | None) -> str | None:
    return CURRENCIES.get(nfc(token.lower().rstrip("."))) if token else None


def _cue_before(prefix: str) -> str | None:
    last = None
    for last in _BOUNDARY.finditer(prefix[-100:]):
        pass
    segment = prefix[-100:][last.end() :] if last else prefix[-100:]
    m = _BEFORE.search(segment)
    return (m["c"] or m["at"]).lower() if m else None


def parse_amounts(text: str, *, units: Iterable[str] = ()) -> list[AmountMatch]:
    """Money amounts in ``text``. ``units`` are extra unit words ("200 shirts" is a quantity, not money)."""
    nz = normalize(text)
    t = nz.text
    not_money_next = re.compile(
        rf"\s*(?:{alternation([*BUILTIN_UNITS, *TIME_WORDS, *units])}|{MONTH_RE}){NOT_BEFORE}", re.IGNORECASE
    )
    found: list[tuple[int, AmountMatch]] = []
    taken: list[tuple[int, int]] = []

    for m in _RANGE.finditer(t):
        cur = _currency(m["cp"] or m["cp2"] or m["cs"])
        if not (cur or m["mb"]):
            continue
        low, high = _paise(m["a"], m["ma"] or m["mb"]), _paise(m["b"], m["mb"])
        found.append((m.start(), AmountMatch(**nz.locate(m.start(), m.end()), paise=None, currency=cur or "INR", approximate=True, is_range=True, low_paise=low, high_paise=high)))
        taken.append((m.start(), m.end()))

    for m in _AMOUNT.finditer(t):
        if any(s < m.end() and m.start() < e for s, e in taken):
            continue
        magnitude = m["m"] or m["wm"]
        if m["w"]:
            paise = int((NUMBER_WORDS[nfc(m["w"].lower())] * MAGNITUDES[nfc(magnitude.lower())] * 100).to_integral_value(ROUND_HALF_UP))
        else:
            paise = _paise(m["n"], m["m"])
        cur = _currency(m["cp"] or m["cs"])
        before = _cue_before(t[: m.start()])
        approx = bool(m["tilde"]) or bool(_APPROX.search(t[: m.start()][-30:]))
        after = _AFTER.match(t, m.end())
        per, cue, period = None, before, None
        if after:
            word = after["pu"] or after["su"]
            if after["total"]:
                per, cue = "total", cue or "total"
            elif word and word.lower() in PERIODS:
                period, cue = word.lower().rstrip("s"), cue or "per"
            else:
                per, cue = "item", cue or ("each" if after["each"] else "per")
        if before == "total":
            per = per or "total"
        elif before in ("rate", "@"):
            per = per or "item"
        if not (cur or magnitude):
            digits = re.sub(r"\D", "", (m["n"] or "").split(".")[0])
            if len(digits) >= 10 or not_money_next.match(t, m.end()):
                continue
            if not (cue or (approx and paise >= 100_000)):
                continue
        found.append((m.start(), AmountMatch(**nz.locate(m.start(), m.end()), paise=paise, currency=cur or "INR", per=per, approximate=approx, cue=cue, period=period)))
    return [a for _, a in sorted(found, key=lambda f: f[0])]
