"""Phase 3: text normalisation for the rules engine (AI_SPEC section 2 step 1)."""

from __future__ import annotations

import pytest

from packages.intelligence.normalize import normalize_for_rules


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("५० हज़ार", "50 हज़ार"),
        ("೫೦೦ each", "500 each"),
        ("４８０ each", "480 each"),
        ("200   shirts\t480", "200 shirts 480"),
        ("é", "é"),
        ("", ""),
    ],
)
def test_normalize_for_rules(raw, expected):
    assert normalize_for_rules(raw) == expected


def test_original_text_is_not_mutated():
    raw = "५० हज़ार"
    normalize_for_rules(raw)
    assert raw == "५० हज़ार"


def test_spans_survive_collapsed_whitespace_and_kannada_digits():
    from packages.intelligence.rules import parse_amounts

    raw = "ok\n\n   advance   ೪೮೦೦೦\t sent"
    m = parse_amounts(raw)[0]
    assert m.paise == 4_800_000 and raw[m.start : m.end] == m.raw == "೪೮೦೦೦"


def test_normalize_drops_leading_and_trailing_space():
    assert normalize_for_rules("  \n a  b \t") == "a b"
    assert normalize_for_rules("  x") == "x"


def test_decomposed_and_composed_forms_normalise_the_same():
    assert normalize_for_rules("é") == normalize_for_rules("é") == "é"


def test_parser_spans_refer_to_original_text():
    # S4 highlights the exact words, so spans must index the original string, not the normalised one
    from packages.intelligence.rules import parse_amounts

    raw = "ok   advance ४८,००० sent"
    m = parse_amounts(raw)[0]
    assert raw[m.start : m.end] == m.raw
    assert "४८,०००" in m.raw
