"""Phase 1: the worked example of INTEGRITY_SPEC section 6 (values re-computed and confirmed)."""

from __future__ import annotations

from packages.integrity.hashing import TypeByte, canonicalize, leaf_hash, payload_digest_json
from packages.integrity.merkle import merkle_root

PAYLOADS = [
    {"id": 1, "sender": "Asha", "text": "50 mugs, 120 each ok?", "ts": "2026-10-12T10:02:00+05:30"},
    {"id": 2, "sender": "Bilal", "text": "ok. delivery next week", "ts": "2026-10-12T10:04:00+05:30"},
]
SALTS = [bytes([1]) * 16, bytes([2]) * 16, bytes([3]) * 16]

LEAF1 = "eeb767408a78a214391a6ac1741af71f760942fc6a622ac339f71ea353b1a031"
LEAF2 = "fb6c734564c502a8fad2b84a96a5b65ce61c4c4b29d8793ba9415f49aff04ed6"
LEAF3 = "819e4dd2d881aea6aacd2ff2660e87ce2bf6adcdcc61c45d968c90d5d3ec5191"
NODE12 = "8ad7c5b056b23eddce000148d9ec7394369c45848be2680fdf3f6e8f21d63eaa"
ROOT = "eabcf74ed1892907946af628a5c56b54b6ef1ec1fb22746d847fd2fc19eca2a5"


def test_payload_1_canonical_form():
    assert canonicalize(PAYLOADS[0]) == (
        b'{"id":1,"sender":"Asha","text":"50 mugs, 120 each ok?","ts":"2026-10-12T10:02:00+05:30"}'
    )


def test_leaf_1():
    assert leaf_hash(TypeByte.MESSAGE, SALTS[0], payload_digest_json(PAYLOADS[0])).hex() == LEAF1


def test_leaf_2():
    assert leaf_hash(TypeByte.MESSAGE, SALTS[1], payload_digest_json(PAYLOADS[1])).hex() == LEAF2


def test_root_and_node_from_the_three_leaves():
    leaves = [bytes.fromhex(x) for x in (LEAF1, LEAF2, LEAF3)]
    assert merkle_root(leaves[:2]).hex() == NODE12
    assert merkle_root(leaves).hex() == ROOT
