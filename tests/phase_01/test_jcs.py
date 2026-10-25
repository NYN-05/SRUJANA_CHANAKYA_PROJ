"""Phase 1: RFC 8785 JSON canonicalisation (INTEGRITY_SPEC section 4, Q-56)."""

from __future__ import annotations

import json
import math

import pytest

from packages.integrity.hashing import CanonicalizationError, canonicalize


def c(obj) -> str:
    return canonicalize(obj).decode("utf-8")


def test_returns_bytes():
    assert isinstance(canonicalize({"a": 1}), bytes)


def test_keys_sorted_and_no_whitespace():
    assert c({"b": 1, "a": 2, "c": {"z": 1, "y": [3, 2, 1]}}) == '{"a":2,"b":1,"c":{"y":[3,2,1],"z":1}}'


def test_keys_sorted_by_utf16_code_units_not_code_points():
    # U+1F600 is the surrogate pair D83D DE00, which sorts before U+FF5E in UTF-16
    obj = {"～": 1, "\U0001f600": 2}
    assert c(obj) == '{"\U0001f600":2,"～":1}'


def test_unicode_is_not_escaped():
    assert c({"t": "नमस्ते ಕನ್ನಡ ₹"}) == '{"t":"नमस्ते ಕನ್ನಡ ₹"}'
    assert canonicalize({"t": "₹"}) == '{"t":"₹"}'.encode("utf-8")


def test_escapes():
    assert c({"a": "\n\t\"\\/\u001f\b\f\r"}) == '{"a":"\\n\\t\\"\\\\/\\u001f\\b\\f\\r"}'


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "0"),
        (-0.0, "0"),
        (1.0, "1"),
        (4.50, "4.5"),
        (2e-3, "0.002"),
        (1e21, "1e+21"),
        (1e30, "1e+30"),
        (1e-7, "1e-7"),
        (0.000001, "0.000001"),
        (333333333.33333329, "333333333.3333333"),
        (1e-27, "1e-27"),
        (9007199254740991, "9007199254740991"),
        (-9007199254740991, "-9007199254740991"),
    ],
)
def test_number_formatting(value, expected):
    assert c([value]) == f"[{expected}]"


def test_literals_and_empty_containers():
    assert c({"t": True, "f": False, "n": None, "o": {}, "l": []}) == '{"f":false,"l":[],"n":null,"o":{},"t":true}'
    assert c({}) == "{}"
    assert c([]) == "[]"


@pytest.mark.parametrize("bad", [2**53, -(2**53), 10**20, math.nan, math.inf, -math.inf])
def test_rejects_unsafe_numbers(bad):
    with pytest.raises(CanonicalizationError):
        canonicalize({"x": bad})


def test_rejects_non_json_types():
    with pytest.raises((CanonicalizationError, TypeError)):
        canonicalize({"x": b"bytes"})
    with pytest.raises((CanonicalizationError, TypeError)):
        canonicalize({1: "non-string key"})


def test_round_trip_is_stable():
    obj = {"msg": "50 mugs, 120 each ok?", "n": [1, 2.5, "x"], "z": {"a": None}}
    once = canonicalize(obj)
    assert canonicalize(json.loads(once)) == once


def test_rejects_tuples_sets_and_nested_bad_values():
    for bad in ({"x": (1, 2)}, {"x": {1, 2}}, {"x": [{"y": math.nan}]}, {"x": {"y": [2**60]}}):
        with pytest.raises((CanonicalizationError, TypeError)):
            canonicalize(bad)


def test_canonicalization_error_is_a_value_error():
    assert issubclass(CanonicalizationError, ValueError)


def test_bool_is_not_treated_as_an_integer():
    assert c([True, False, 1, 0]) == "[true,false,1,0]"
