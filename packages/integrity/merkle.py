"""Salted Merkle tree with odd carry-up (INTEGRITY_SPEC section 6, Q-60)."""

from __future__ import annotations

from collections.abc import Sequence

from .hashing import TypeByte, sha256

_NODE = bytes([TypeByte.MERKLE_NODE])


class EmptyTreeError(ValueError):
    """A tree needs at least one leaf; a receipt cannot cover nothing."""


def _node(left: bytes, right: bytes) -> bytes:
    return sha256(_NODE + left + right)


def _levels(leaves: Sequence[bytes]) -> list[list[bytes]]:
    """Every level from the leaves up; an odd last node is carried up unchanged, never duplicated."""
    if not leaves:
        raise EmptyTreeError("an empty tree has no root")
    if any(not isinstance(leaf, (bytes, bytearray)) or len(leaf) != 32 for leaf in leaves):
        raise ValueError("every leaf must be a raw 32-byte hash")
    levels = [[bytes(leaf) for leaf in leaves]]
    while len(level := levels[-1]) > 1:
        nxt = [_node(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])
        levels.append(nxt)
    return levels


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    return _levels(leaves)[-1][0]


def inclusion_proof(leaves: Sequence[bytes], index: int) -> list[tuple[str, bytes]]:
    """Sibling hashes from the bottom up with their side; a carried level adds no entry."""
    levels = _levels(leaves)
    if not 0 <= index < len(leaves):
        raise IndexError(f"leaf index {index} out of range")
    proof = []
    for level in levels[:-1]:
        if index % 2:
            proof.append(("left", level[index - 1]))
        elif index + 1 < len(level):
            proof.append(("right", level[index + 1]))
        index //= 2
    return proof


def verify_inclusion(leaf: bytes, proof: Sequence[tuple[str, bytes]], root: bytes) -> bool:
    current = leaf
    for side, sibling in proof:
        if side == "left":
            current = _node(sibling, current)
        elif side == "right":
            current = _node(current, sibling)
        else:
            return False
    return current == root
