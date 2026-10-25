"""Phase 1: salted Merkle tree with odd carry-up (INTEGRITY_SPEC section 6, Q-60)."""

from __future__ import annotations

import hashlib

import pytest

from packages.integrity.merkle import EmptyTreeError, inclusion_proof, merkle_root, verify_inclusion

SIZES = [1, 2, 3, 4, 5, 7, 9, 16]


def H(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def node(left: bytes, right: bytes) -> bytes:
    return H(b"\x01" + left + right)


def reference_root(leaves: list[bytes]) -> bytes:
    """Independent reference: pair left to right, carry an odd last node up unchanged."""
    level = list(leaves)
    while len(level) > 1:
        nxt = [node(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def leaves_of(n: int) -> list[bytes]:
    return [H(f"leaf-{i}".encode()) for i in range(n)]


@pytest.mark.parametrize("n", SIZES)
def test_root_matches_reference(n):
    leaves = leaves_of(n)
    assert merkle_root(leaves) == reference_root(leaves)


def test_one_leaf_root_is_the_leaf_and_proof_is_empty():
    leaf = leaves_of(1)
    assert merkle_root(leaf) == leaf[0]
    assert inclusion_proof(leaf, 0) == []
    assert verify_inclusion(leaf[0], [], leaf[0])


def test_three_leaves_carry_up_not_duplicate():
    a, b, c = leaves_of(3)
    assert merkle_root([a, b, c]) == node(node(a, b), c)
    assert merkle_root([a, b, c]) != node(node(a, b), node(c, c))


def test_empty_tree_rejected():
    with pytest.raises(EmptyTreeError):
        merkle_root([])


@pytest.mark.parametrize("n", SIZES)
def test_every_inclusion_proof_verifies(n):
    leaves = leaves_of(n)
    root = merkle_root(leaves)
    for i, leaf in enumerate(leaves):
        proof = inclusion_proof(leaves, i)
        assert all(side in ("left", "right") and len(h) == 32 for side, h in proof)
        assert verify_inclusion(leaf, proof, root), f"proof {i} of {n} failed"


def test_proof_has_no_entry_for_carried_level():
    leaves = leaves_of(3)
    # leaf 2 is carried up at level 0, then paired with node(0,1): exactly one sibling
    proof = inclusion_proof(leaves, 2)
    assert proof == [("left", node(leaves[0], leaves[1]))]


def test_proof_sides_for_four_leaves():
    a, b, c, d = leaves_of(4)
    assert inclusion_proof([a, b, c, d], 0) == [("right", b), ("right", node(c, d))]
    assert inclusion_proof([a, b, c, d], 3) == [("left", c), ("left", node(a, b))]


def test_tampered_proof_or_leaf_fails():
    leaves = leaves_of(5)
    root = merkle_root(leaves)
    proof = inclusion_proof(leaves, 1)
    assert not verify_inclusion(H(b"other"), proof, root)
    side, sib = proof[0]
    flipped = [("left" if side == "right" else "right", sib), *proof[1:]]
    assert not verify_inclusion(leaves[1], flipped, root)


def test_order_matters():
    a, b = leaves_of(2)
    assert merkle_root([a, b]) != merkle_root([b, a])


def test_proof_index_out_of_range():
    with pytest.raises((IndexError, ValueError)):
        inclusion_proof(leaves_of(3), 3)


def test_leaves_must_be_32_bytes():
    with pytest.raises(ValueError):
        merkle_root([b"short"])


def test_unknown_proof_side_fails():
    leaves = leaves_of(2)
    _, sibling = inclusion_proof(leaves, 0)[0]
    assert not verify_inclusion(leaves[0], [("up", sibling)], merkle_root(leaves))


def test_empty_tree_error_is_a_value_error_and_proof_of_empty_tree_rejected():
    assert issubclass(EmptyTreeError, ValueError)
    with pytest.raises(EmptyTreeError):
        inclusion_proof([], 0)
    with pytest.raises((IndexError, ValueError)):
        inclusion_proof(leaves_of(3), -1)
