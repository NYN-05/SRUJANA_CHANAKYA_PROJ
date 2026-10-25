"""Phase 4: money and date formatting (FR-RCP-001 rules; I-07, I-17)."""

from __future__ import annotations

from datetime import date

import pytest

from packages.contracts.formatting import format_date, format_inr


@pytest.mark.parametrize(
    "paise,text",
    [
        (0, "₹0"),
        (48_000, "₹480"),
        (4_800_000, "₹48,000"),
        (9_600_000, "₹96,000"),
        (10_000_000, "₹1,00,000"),
        (15_000_000, "₹1,50,000"),
        (1_234_567_800, "₹1,23,45,678"),
        (123_450, "₹1,234.50"),
        (5, "₹0.05"),
        ("4800000", "₹48,000"),
    ],
)
def test_format_inr_indian_grouping(paise, text):
    assert format_inr(paise) == text


def test_format_inr_rejects_negative_and_bad_input():
    for bad in (-1, "12.5", "abc"):
        with pytest.raises(ValueError):
            format_inr(bad)


@pytest.mark.parametrize(
    "d,lang,text",
    [
        (date(2026, 11, 15), "en", "15 Nov 2026"),
        (date(2026, 1, 5), "en", "5 Jan 2026"),
        (date(2026, 9, 30), "en", "30 Sep 2026"),
        (date(2026, 11, 15), "hi", "15 नवंबर 2026"),
        (date(2026, 1, 5), "hi", "5 जनवरी 2026"),
    ],
)
def test_format_date(d, lang, text):
    assert format_date(d, lang) == text


def test_format_date_accepts_iso_text():
    assert format_date("2026-11-15", "en") == "15 Nov 2026"


def test_format_date_unknown_language():
    with pytest.raises(ValueError):
        format_date(date(2026, 11, 15), "xx")
