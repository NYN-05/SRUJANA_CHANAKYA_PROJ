"""Phase 2: date-order inference (FR-IMP-001 last rule)."""

from __future__ import annotations

from datetime import date

from packages.ingest.whatsapp import parse_export


def parse(text: str, **kw):
    return parse_export(text.encode("utf-8"), **kw)


def test_day_first_inferred_from_value_above_12():
    r = parse("01/02/26, 09:00 - Raju: a\n13/02/26, 09:00 - Meena: b\n")
    assert r.date_order == "DMY" and not r.needs_date_order_choice
    assert r.messages[0].ts.date() == date(2026, 2, 1)


def test_month_first_inferred_from_second_field_above_12():
    r = parse("01/02/26, 09:00 - Raju: a\n02/13/26, 09:00 - Meena: b\n")
    assert r.date_order == "MDY"
    assert r.messages[0].ts.date() == date(2026, 1, 2)
    assert r.messages[1].ts.date() == date(2026, 2, 13)


def test_unknown_order_asks_the_user_and_does_not_guess():
    r = parse("01/02/26, 09:00 - Raju: a\n03/04/26, 09:00 - Meena: b\n")
    assert r.date_order is None
    assert r.needs_date_order_choice is True
    assert all(m.ts is None for m in r.messages)
    assert [m.text for m in r.messages] == ["a", "b"]


def test_explicit_order_wins_over_inference():
    r = parse("01/02/26, 09:00 - Raju: a\n03/04/26, 09:00 - Meena: b\n", date_order="MDY")
    assert r.date_order == "MDY" and not r.needs_date_order_choice
    assert r.messages[1].ts.date() == date(2026, 3, 4)


def test_mixed_orders_warn_and_ask():
    r = parse("13/02/26, 09:00 - Raju: a\n02/13/26, 09:00 - Meena: b\n")
    assert r.date_order is None and r.needs_date_order_choice
    assert "mixed_date_order" in r.warnings


def test_explicit_order_that_makes_dates_impossible_is_reported():
    r = parse("13/02/26, 09:00 - Raju: a\n", date_order="MDY")
    assert r.unparsed_lines and r.unparsed_lines[0][0] == 1
