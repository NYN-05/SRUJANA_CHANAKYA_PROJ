"""Phase 3: parsers never raise on any text and stay fast (PHASES.md Phase 3, error handling; AC-3.5)."""

from __future__ import annotations

import random
import time
from datetime import date

from packages.intelligence.normalize import normalize_for_rules
from packages.intelligence.rules import (
    parse_amounts,
    parse_dates,
    parse_payment_phrases,
    parse_penalty_phrases,
    parse_percentages,
    parse_quantities,
)

PIECES = [
    "₹", "Rs.", "50k", "1.5 lakh", "१५", "೩೦", "０９", "pachaas hazaar", "dedh lakh", "15/11/2026", "03/04", "31/02/2026",
    "Nov", "नवंबर", "next week", "per day", "late fee", "30 din baad", "on delivery", "half", "aadha", "%", " - ", "to",
    "9876543210", "raju@okaxis", "\x00", "🙂", "‎", " ", "\n", "\t", "a" * 40, "1" * 30, ",", ".", "/", "#", "~",
]


def test_no_parser_raises_on_random_text():
    rng = random.Random(20261025)
    for _ in range(1500):
        text = "".join(rng.choice(PIECES) + rng.choice([" ", "", "  "]) for _ in range(rng.randint(0, 25)))
        for found in (
            parse_amounts(text),
            parse_quantities(text),
            parse_dates(text, reference=date(2026, 10, 12), date_order=rng.choice([None, "DMY", "MDY"])),
            parse_percentages(text),
            parse_payment_phrases(text),
            parse_penalty_phrases(text),
        ):
            for m in found:
                assert 0 <= m.start <= m.end <= len(text) and m.raw == text[m.start : m.end]
        normalize_for_rules(text)


def test_pathological_inputs_are_fast():
    texts = ["1," * 5000, "lakh " * 5000, "9" * 20000, "per day " * 5000, " " * 50000 + "480 each", "15/" * 5000, "₹ " * 5000]
    start = time.perf_counter()
    for text in texts:
        parse_amounts(text)
        parse_quantities(text)
        parse_dates(text, reference=date(2026, 10, 12), date_order=None)
        parse_payment_phrases(text)
        parse_penalty_phrases(text)
        parse_percentages(text)
    assert time.perf_counter() - start < 5
