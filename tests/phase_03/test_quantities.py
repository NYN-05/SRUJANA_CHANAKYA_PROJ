"""Phase 3: quantity parser (AI_SPEC section 3)."""

from __future__ import annotations

import pytest

from packages.intelligence.rules import parse_quantities


@pytest.mark.parametrize(
    "text,amount,unit",
    [
        ("200 shirts, 480 each ok?", 200, "shirts"),
        ("need 500 banners", 500, "banners"),
        ("100 bags of cement", 100, "bags"),
        ("50 pcs", 50, "pcs"),
        ("5 kg", 5, "kg"),
        ("2 dozen shirts", 24, "shirts"),
        ("300 mugs chahiye", 300, "mugs"),
        ("१०० shirts", 100, "shirts"),
    ],
)
def test_quantity(text, amount, unit):
    found = parse_quantities(text)
    assert found and found[0].amount == amount and found[0].unit == unit
    assert found[0].vague is False


def test_zero_and_decimals():
    zero = parse_quantities("0 shirts")
    assert zero and zero[0].amount == 0
    assert parse_quantities("2.5 kg") == []
    assert parse_quantities("2.0 kg")[0].amount == 2


def test_playbook_units_extend_the_builtin_list():
    assert parse_quantities("2 revisions") == []
    assert parse_quantities("2 revisions", units=["revisions"])[0].unit == "revisions"


def test_dozen_without_a_unit_and_vague_without_a_unit_word():
    assert parse_quantities("3 dozen")[0].amount == 36
    assert parse_quantities("some time later") == []


def test_spans_point_at_original_text():
    text = "ok  २०० shirts"
    m = parse_quantities(text)[0]
    assert text[m.start : m.end] == m.raw == "२०० shirts"


@pytest.mark.parametrize("text", ["some shirts", "a few pieces", "as needed", "zarurat ke hisaab se"])
def test_vague_quantity(text):
    found = parse_quantities(text)
    assert found and found[0].vague is True and found[0].amount is None


@pytest.mark.parametrize("text", ["480 each", "₹48,000", "at 10:30", "delivery by 15 Nov", "9876543210"])
def test_not_a_quantity(text):
    assert parse_quantities(text) == []
