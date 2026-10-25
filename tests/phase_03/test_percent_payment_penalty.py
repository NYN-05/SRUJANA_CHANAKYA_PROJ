"""Phase 3: percentages, payment phrases and penalty phrases (AI_SPEC section 3)."""

from __future__ import annotations

import pytest

from packages.intelligence.rules import parse_payment_phrases, parse_penalty_phrases, parse_percentages


@pytest.mark.parametrize("text,bp", [("50%", 5000), ("advance half now", 5000), ("aadha advance de diya", 5000), ("adha", 5000), ("25 %", 2500), ("10 percent", 1000)])
def test_percentages(text, bp):
    found = parse_percentages(text)
    assert found and found[0].basis_points == bp


def test_no_percentage():
    assert parse_percentages("200 shirts at 480") == []


@pytest.mark.parametrize(
    "text,kind,days,vague",
    [
        ("balance on delivery", "on_delivery", None, False),
        ("pay after delivery", "after_delivery", None, False),
        ("balance within 30 days of delivery", "net_days", 30, False),
        ("30 days after delivery", "net_days", 30, False),
        ("baaki 30 din baad", "net_days", 30, False),
        ("advance 20,000 today", "advance", None, False),
        ("in 3 instalments", "instalments", None, False),
        ("will pay soon", "later", None, True),
        ("baad mein de dunga", "later", None, True),
        ("when I can", "later", None, True),
    ],
)
def test_payment_phrases(text, kind, days, vague):
    found = parse_payment_phrases(text)
    assert found, text
    m = found[0]
    assert (m.kind, m.days, m.vague) == (kind, days, vague)


@pytest.mark.parametrize(
    "text,kind",
    [
        ("If delivery is late, 500 per day deduction.", "per_day"),
        ("late fee of 1000", "late_fee"),
        ("penalty 2% per week", "penalty"),
        ("we will deduct 5% if late", "deduction"),
    ],
)
def test_penalty_phrases(text, kind):
    found = parse_penalty_phrases(text)
    assert found and found[0].kind == kind


def test_no_penalty():
    assert parse_penalty_phrases("delivery next week") == []


def test_decimal_percentage_and_spans():
    text = "ok 2.5 % fee"
    m = parse_percentages(text)[0]
    assert m.basis_points == 250 and text[m.start : m.end] == m.raw


def test_net_days_priority_over_after_delivery():
    found = parse_payment_phrases("balance 30 days after delivery")
    assert [(m.kind, m.days) for m in found] == [("net_days", 30)]


def test_on_completion_and_hindi_delivery():
    assert parse_payment_phrases("rest on completion")[0].kind == "on_completion"
    assert parse_payment_phrases("बाकी डिलीवरी पर")[0].kind == "on_delivery"


def test_word_fine_is_not_a_penalty():
    assert parse_penalty_phrases("ok fine, send it") == []


def test_parsers_never_raise_on_odd_text():
    odd = ["\x00", "🙂" * 1000, "%" * 500, "lakh lakh lakh", "₹₹₹", "30 din baad baad baad", "per day per day"]
    for text in odd:
        parse_percentages(text)
        parse_payment_phrases(text)
        parse_penalty_phrases(text)
