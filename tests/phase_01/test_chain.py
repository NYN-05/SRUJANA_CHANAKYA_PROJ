"""Phase 1: version chain (INTEGRITY_SPEC section 8, FR-VLT-003)."""

from __future__ import annotations

import hashlib

import pytest

from packages.integrity.chain import chain_link, terms_digest
from packages.integrity.hashing import canonicalize, normalize_record


def H(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def terms_set(n: int, delivery: str) -> dict:
    return {
        "deal_id": "d1",
        "version_n": n,
        "playbook": {"key": "supply_order", "version": 1},
        "terms": [
            {"key": "delivery_date", "value": {"kind": "date", "date": delivery}},
            {"key": "price", "value": {"kind": "money", "paise": "48000", "per": "item"}},
        ],
    }


ROOTS = [H(b"root-1"), H(b"root-2"), H(b"root-3")]
SETS = [terms_set(1, "2026-11-08"), terms_set(2, "2026-11-15"), terms_set(3, "2026-11-15")]


def build_chain(sets, roots):
    links, prev = [], None
    for s, r in zip(sets, roots):
        link = chain_link(prev, terms_digest(s), r)
        links.append(link)
        prev = link
    return links


def test_terms_digest_formula():
    s = SETS[0]
    assert terms_digest(s) == H(b"\x20" + canonicalize(normalize_record(s)))


def test_first_link_uses_32_zero_bytes():
    td = terms_digest(SETS[0])
    assert chain_link(None, td, ROOTS[0]) == H(b"\x30" + bytes(32) + td + ROOTS[0])


def test_later_link_formula():
    links = build_chain(SETS, ROOTS)
    td2 = terms_digest(SETS[1])
    assert links[1] == H(b"\x30" + links[0] + td2 + ROOTS[1])


def test_three_version_chain_is_deterministic():
    assert build_chain(SETS, ROOTS) == build_chain(SETS, ROOTS)


@pytest.mark.parametrize("changed", [0, 1])
def test_changing_an_earlier_version_breaks_every_later_link(changed):
    good = build_chain(SETS, ROOTS)
    sets = [dict(s) for s in SETS]
    sets[changed] = terms_set(changed + 1, "2026-12-31")
    bad = build_chain(sets, ROOTS)
    for i in range(changed, 3):
        assert bad[i] != good[i]
    for i in range(changed):
        assert bad[i] == good[i]


def test_changing_an_earlier_root_breaks_later_links():
    good = build_chain(SETS, ROOTS)
    bad = build_chain(SETS, [H(b"other"), *ROOTS[1:]])
    assert all(b != g for b, g in zip(bad, good))


def test_array_order_is_significant_so_builders_must_sort_terms_by_key():
    # JCS keeps array order; the record builder (Phase 5) sorts terms by key (INTEGRITY_SPEC 4.2)
    s = terms_set(1, "2026-11-08")
    flipped = dict(s, terms=list(reversed(s["terms"])))
    assert terms_digest(s) != terms_digest(flipped)


@pytest.mark.parametrize("bad", [b"", bytes(31), "00" * 32])
def test_operands_must_be_raw_32_bytes(bad):
    td = terms_digest(SETS[0])
    with pytest.raises((ValueError, TypeError)):
        chain_link(bad, td, ROOTS[0])
    with pytest.raises((ValueError, TypeError)):
        chain_link(None, td, bad)
