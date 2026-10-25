"""Phase 1: receipt hash over the body only (INTEGRITY_SPEC section 9, D2, I-09)."""

from __future__ import annotations

import hashlib

from packages.integrity.hashing import canonicalize, normalize_record
from packages.integrity.receipt import SPEC_VERSION, receipt_hash

BODY = {
    "spec_version": "x",
    "deal_id": "d1",
    "leaf_count": 3,
    "root": "eabcf74ed1892907946af628a5c56b54b6ef1ec1fb22746d847fd2fc19eca2a5",
    "chain": [],
    "recorded_at": "2026-10-24T11:42:00+05:30",
    "anchor": None,
    "import_record_hash": "a" * 64,
}


def test_spec_version_is_set():
    assert isinstance(SPEC_VERSION, str) and SPEC_VERSION


def test_receipt_hash_formula():
    expected = hashlib.sha256(b"\x40" + canonicalize(normalize_record(BODY))).digest()
    assert receipt_hash(BODY) == expected


def test_field_order_irrelevant():
    assert receipt_hash(dict(reversed(list(BODY.items())))) == receipt_hash(BODY)


def test_any_body_change_changes_hash():
    for key, value in [("leaf_count", 4), ("root", "b" * 64), ("anchor", {"network": "x", "tx": "y", "block_time": "z"})]:
        assert receipt_hash(dict(BODY, **{key: value})) != receipt_hash(BODY)
