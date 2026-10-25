"""Version chain (INTEGRITY_SPEC section 8, FR-VLT-003)."""

from __future__ import annotations

from typing import Any

from .hashing import TypeByte, plain_hash, require_bytes, sha256

_ZERO_LINK = bytes(32)


def terms_digest(terms_set: dict[str, Any]) -> bytes:
    """H(0x20 || JCS(terms_set)); the record builder sorts terms by key (INTEGRITY_SPEC 4.2)."""
    return plain_hash(TypeByte.TERMS_SET, terms_set)


def chain_link(prev_link: bytes | None, digest: bytes, root: bytes) -> bytes:
    """link_n = H(0x30 || link_(n-1) || terms_digest_n || root_n); link_0 uses 32 zero bytes."""
    prev = _ZERO_LINK if prev_link is None else require_bytes(prev_link, 32, "previous link")
    return sha256(
        bytes([TypeByte.CHAIN_LINK]) + prev + require_bytes(digest, 32, "terms digest") + require_bytes(root, 32, "root")
    )
