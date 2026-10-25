"""Phase 1: normalize_text and normalize_record (INTEGRITY_SPEC section 2, Q-55)."""

from __future__ import annotations

import pytest

from packages.integrity.hashing import canonicalize, normalize_record, normalize_text


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("é", "é"),  # combining acute to precomposed
        ("a\r\nb", "a\nb"),
        ("a\rb", "a\nb"),
        ("a\r\n\r\nb", "a\n\nb"),
        ("नमस्ते", "नमस्ते"),  # already NFC
        ("ಕನ್ನಡ", "ಕನ್ನಡ"),
        ("", ""),
        ("no change", "no change"),
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_normalize_text_does_not_trim_or_collapse():
    assert normalize_text("  two  spaces  ") == "  two  spaces  "


def test_normalize_record_changes_values_not_keys():
    rec = {"é": "é", "n": 5, "list": ["a\r\nb", {"k": "é"}], "none": None, "flag": True}
    out = normalize_record(rec)
    assert "é" in out, "keys are never normalised"
    assert out["é"] == "é"
    assert out["list"] == ["a\nb", {"k": "é"}]
    assert out["n"] == 5 and out["none"] is None and out["flag"] is True


def test_normalize_record_does_not_mutate_input():
    rec = {"a": "é"}
    normalize_record(rec)
    assert rec == {"a": "é"}


def test_canonicalize_itself_does_not_normalise():
    # JCS is pure RFC 8785: the decomposed form survives canonicalisation
    assert canonicalize({"a": "é"}) == '{"a":"é"}'.encode("utf-8")
