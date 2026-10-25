"""Receipt hash over the body only (INTEGRITY_SPEC section 9, D2)."""

from __future__ import annotations

from typing import Any

from .hashing import TypeByte, plain_hash

# 1.1 adds import_record_hash to the receipt body (I-09); byte values are unchanged from 1.0.
SPEC_VERSION = "1.1"


def receipt_hash(body: dict[str, Any]) -> bytes:
    """H(0x40 || JCS(body)); the hash sits outside the body in the envelope, so it never hashes itself."""
    return plain_hash(TypeByte.RECEIPT, body)
