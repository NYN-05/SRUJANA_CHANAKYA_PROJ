"""Phase 1: echo code derivation and reply matching (INTEGRITY_SPEC section 7, I-08, FR-ECH-001)."""

from __future__ import annotations

import hashlib
import random

import pytest

from packages.integrity.echo import ALPHABET, codes_match, echo_code, extract_code, recap_hash
from packages.integrity.hashing import canonicalize, normalize_record


def H(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def reference_code(rh: bytes) -> str:
    digest = H(b"\x50" + rh)
    bits = int.from_bytes(digest[:3], "big") >> 4  # first 20 bits
    return "".join(ALPHABET[(bits >> shift) & 0x1F] for shift in (15, 10, 5, 0))


RECAP = {
    "deal_id": "d1",
    "version_n": 1,
    "language": "en",
    "lines": [
        {"term_key": "price", "text": "200 shirts at ₹480 each = ₹96,000", "sources": ["m1"]},
        {"term_key": "advance", "text": "₹48,000 advance received", "sources": ["m4"]},
    ],
    "body_text": "Hi Meena, just confirming what we discussed:\n• 200 shirts at ₹480 each = ₹96,000\n• ₹48,000 advance received",
}


def test_alphabet_is_crockford_base32():
    assert ALPHABET == "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    assert len(set(ALPHABET)) == 32


def test_recap_hash_formula():
    assert recap_hash(RECAP) == H(b"\x21" + canonicalize(normalize_record(RECAP)))


def test_code_derivation_matches_reference():
    rh = recap_hash(RECAP)
    code = echo_code(rh)
    assert code == reference_code(rh)
    assert len(code) == 4 and all(ch in ALPHABET for ch in code)


def test_code_is_deterministic():
    assert echo_code(recap_hash(RECAP)) == echo_code(recap_hash(dict(RECAP)))


def test_code_requires_raw_32_byte_hash():
    with pytest.raises((ValueError, TypeError)):
        echo_code(recap_hash(RECAP).hex())
    with pytest.raises((ValueError, TypeError)):
        echo_code(b"short")


def test_one_character_change_changes_the_code_almost_always():
    rng = random.Random(20261025)
    same = 0
    trials = 500
    for i in range(trials):
        text = f"Delivery by {rng.randint(1, 28)} Nov 2026, item {i}"
        a = dict(RECAP, body_text=text)
        pos = rng.randrange(len(text))
        changed = text[:pos] + ("X" if text[pos] != "X" else "Y") + text[pos + 1 :]
        b = dict(RECAP, body_text=changed)
        same += echo_code(recap_hash(a)) == echo_code(recap_hash(b))
    assert same <= 2, "20-bit codes collide about once in a million"


@pytest.mark.parametrize(
    "reply,expected",
    [
        ("CONFIRM 7F3K", "7F3K"),
        ("confirm 7f3k", "7F3K"),
        ("  Confirm    7F3K  ", "7F3K"),
        ("ok confirm 7f3k thanks", "7F3K"),
        ("CONFIRM 7F3K\n", "7F3K"),
        ("CONFIRM O1LI", "0111"),  # O->0, I->1, L->1 on the code token only
        ("CONFIRM", None),
        ("CONFIRMED", None),
        ("ok 7F3K", None),
        ("", None),
    ],
)
def test_extract_code(reply, expected):
    assert extract_code(reply) == expected


def test_word_confirm_is_not_mangled_by_character_mapping():
    # I-08: mapping O->0 must not apply to the word CONFIRM itself
    assert extract_code("CONFIRM ABCD") == "ABCD"


def test_codes_match():
    assert codes_match("confirm 7f3k", "7F3K")
    assert not codes_match("CONFIRM 7F3L", "7F3K")
    assert not codes_match("no code here", "7F3K")


def test_code_with_letter_u_never_matches():
    # U is not in the Crockford alphabet
    assert not codes_match("CONFIRM 7F3U", "7F3V")
