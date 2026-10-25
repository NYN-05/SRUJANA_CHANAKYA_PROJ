"""Phase 3: date parser (FR-EXT-003; playbook ambiguity rules rel_date, partial_date, order_date)."""

from __future__ import annotations

from datetime import date

import pytest

from packages.intelligence.rules import parse_dates

REF = date(2026, 10, 12)


def one(text, order="DMY", ref=REF):
    found = parse_dates(text, reference=ref, date_order=order)
    assert len(found) == 1, f"{text!r}: {found}"
    return found[0]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Delivery by 15 Nov 2026", date(2026, 11, 15)),
        ("by 15 November 2026", date(2026, 11, 15)),
        ("Nov 15, 2026", date(2026, 11, 15)),
        ("15/11/2026", date(2026, 11, 15)),
        ("15-11-2026", date(2026, 11, 15)),
        ("15.11.26", date(2026, 11, 15)),
        ("delivery on 20/11/2026", date(2026, 11, 20)),
        ("15 नवंबर 2026", date(2026, 11, 15)),
    ],
)
def test_absolute(text, expected):
    m = one(text)
    assert m.kind == "absolute" and m.value == expected and m.rule_id is None


def test_known_order_resolves_numeric_dates():
    assert one("05/11/2026", order="DMY").value == date(2026, 11, 5)
    assert one("05/11/2026", order="MDY").value == date(2026, 5, 11)


def test_unknown_order_gives_both_readings():
    m = one("03/04/2026", order=None)
    assert m.kind == "ambiguous_order" and m.value is None
    assert set(m.readings) == {date(2026, 4, 3), date(2026, 3, 4)}
    assert m.rule_id == "order_date"


def test_unknown_order_with_only_one_valid_reading_is_absolute():
    m = one("25/04/2026", order=None)
    assert m.kind == "absolute" and m.value == date(2026, 4, 25)


@pytest.mark.parametrize("text", ["next week", "delivery next week", "this month", "soon", "kal", "parso", "jaldi", "ASAP", "end of month"])
def test_relative(text):
    m = one(text)
    assert m.kind == "relative" and m.value is None and m.rule_id == "rel_date"


def test_partial_day_without_month():
    m = one("deliver on the 15th")
    assert m.kind == "partial" and m.value is None and m.rule_id == "partial_date"


def test_month_day_without_year_takes_next_occurrence():
    assert one("15 Nov").value == date(2026, 11, 15)
    assert one("5 Jan", ref=date(2026, 12, 20)).value == date(2027, 1, 5)
    assert one("5 Nov works").value == date(2026, 11, 5)


def test_impossible_date_is_not_a_date():
    assert parse_dates("31/02/2026", reference=REF, date_order="DMY") == []


def test_iso_date():
    assert one("deliver 2026-11-15").value == date(2026, 11, 15)


def test_ordinal_with_month_is_a_full_date_not_partial():
    m = one("by 15th Nov")
    assert m.kind == "absolute" and m.value == date(2026, 11, 15)


def test_reference_day_itself_counts_as_this_year():
    assert one("12 Oct").value == date(2026, 10, 12)
    assert one("11 Oct").value == date(2027, 10, 11)


def test_29_february_without_year_finds_the_next_leap_year():
    assert one("29 Feb", ref=date(2026, 3, 1)).value == date(2028, 2, 29)


def test_month_first_and_day_first_text_dates_agree():
    assert one("Nov 15 2026").value == one("15 Nov 2026").value == date(2026, 11, 15)


def test_two_dates_in_one_message_in_order():
    found = parse_dates("from 1 Nov 2026 to 15 Nov 2026", reference=REF, date_order="DMY")
    assert [d.value for d in found] == [date(2026, 11, 1), date(2026, 11, 15)]


def test_month_words_inside_other_words_are_not_dates():
    assert parse_dates("5 market stalls and 3 decimals", reference=REF, date_order="DMY") == []


def test_spans_point_at_original_text():
    text = "ok   delivery on १५ नवंबर 2026 thanks"
    m = parse_dates(text, reference=REF, date_order="DMY")[0]
    assert text[m.start : m.end] == m.raw and m.value == date(2026, 11, 15)


def test_same_day_and_month_numbers_are_not_ambiguous():
    m = one("05/05/2026", order=None)
    assert m.kind == "absolute" and m.value == date(2026, 5, 5)


@pytest.mark.parametrize("text", ["480 each", "200 shirts", "call at 10:30", "version 1.5", ""])
def test_not_dates(text):
    assert parse_dates(text, reference=REF, date_order="DMY") == []
