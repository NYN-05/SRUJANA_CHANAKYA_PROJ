"""Phase 3: amount parser (FR-EXT-003; AI_SPEC section 3). Values are integer paise."""

from __future__ import annotations

import pytest

from packages.intelligence.rules import parse_amounts

RUPEE = 100


def one(text):
    found = parse_amounts(text)
    assert len(found) == 1, f"{text!r}: {found}"
    return found[0]


@pytest.mark.parametrize(
    "text,rupees",
    [
        ("50k", 50_000),
        ("price 50K", 50_000),
        ("1.5 lakh", 150_000),
        ("1.5 lac", 150_000),
        ("2 crore", 20_000_000),
        ("₹48,000", 48_000),
        ("Rs. 48000/-", 48_000),
        ("Rs 480", 480),
        ("INR 4,800", 4_800),
        ("₹1,50,000", 150_000),
        ("1,50,000 rupees", 150_000),
        ("48 hazaar", 48_000),
        ("pachaas hazaar", 50_000),
        ("das hazaar", 10_000),
        ("dedh lakh", 150_000),
        ("dhai lakh", 250_000),
        ("५० हज़ार", 50_000),
        ("५० हजार", 50_000),
        ("480 each", 480),
        ("done sent 48000", 48_000),
        ("advance 20,000 today", 20_000),
        ("balance 40,000 on delivery", 40_000),
        ("total 60,000.", 60_000),
        ("₹1,234.50", 1_234.50),
    ],
)
def test_amount_values(text, rupees):
    assert one(text).paise == round(rupees * RUPEE)


def test_span_points_at_original_text():
    text = "ok so 480 each then"
    m = one(text)
    assert text[m.start : m.end].startswith("480")
    assert m.raw == text[m.start : m.end]


def test_per_item_marker():
    assert one("480 each").per == "item"
    assert one("rate 120 per piece").per == "item"
    assert one("@ 120").per == "item"
    assert one("Price 50,000 total").per == "total"


@pytest.mark.parametrize("text", ["approx 50k", "around 50,000", "about ₹50,000", "lagbhag 50 hazaar", "~50k"])
def test_approximate(text):
    assert one(text).approximate is True


def test_exact_is_not_approximate():
    assert one("₹50,000").approximate is False


@pytest.mark.parametrize("text,low,high", [("40 to 50k", 40_000, 50_000), ("40-50k", 40_000, 50_000), ("8 to 10k", 8_000, 10_000)])
def test_ranges(text, low, high):
    m = one(text)
    assert m.is_range is True
    assert (m.low_paise, m.high_paise) == (low * RUPEE, high * RUPEE)


@pytest.mark.parametrize("text", ["$480", "480 USD", "USD 480"])
def test_foreign_currency_marked(text):
    assert one(text).currency == "USD"


def test_rupee_default_currency():
    assert one("₹480").currency == "INR"
    assert one("480 each").currency == "INR"


@pytest.mark.parametrize(
    "text",
    [
        "200 shirts",
        "call me on 9876543210",
        "pay to raju@okaxis",
        "order #4521",
        "see you at 10:30",
        "on 15/11/2026",
        "",
    ],
)
def test_not_money(text):
    assert parse_amounts(text) == []


def test_tilde_is_part_of_the_span():
    text = "price ~50k ok"
    m = one(text)
    assert text[m.start : m.end] == "~50k" and m.approximate


@pytest.mark.parametrize("text", ["10-12 shirts", "15-11-2026", "call 100-200", "pay on 3/4 Nov"])
def test_digits_that_look_like_ranges_are_not_money(text):
    assert parse_amounts(text) == []


@pytest.mark.parametrize("text", ["advance 20 Oct", "sent 3 shirts", "balance within 30 days", "paid 5 hours ago"])
def test_cue_before_a_unit_month_or_duration_is_not_money(text):
    assert parse_amounts(text) == []


def test_extra_units_are_not_money():
    assert parse_amounts("rate 2 revisions") != []
    assert parse_amounts("rate 2 revisions", units=["revisions"]) == []


def test_long_digit_runs_need_a_currency_marker():
    assert parse_amounts("sent 9876543210") == []
    assert one("₹9876543210").paise == 987_654_321_000


def test_per_time_marks_a_period_not_a_unit_price():
    m = one("If late, 500 per day")
    assert m.period == "day" and m.per is None and m.paise == 50_000


def test_percent_is_not_money():
    assert parse_amounts("penalty 2% per week") == []


def test_amount_with_trailing_full_stop():
    assert one("total 60,000.").paise == 6_000_000


def test_huge_numbers_do_not_raise():
    parse_amounts("₹" + "9" * 5000)
    parse_amounts("1" * 40 + " lakh")


def test_hindi_number_words_need_a_magnitude():
    assert parse_amounts("sau") == [] and parse_amounts("do teen") == []
    assert one("do hazaar").paise == 200_000


def test_two_amounts_in_one_message():
    found = parse_amounts("Advance 20,000 today, balance 40,000 on delivery.")
    assert [m.paise for m in found] == [2_000_000, 4_000_000]
    assert [m.cue for m in found] == ["advance", "balance"]
