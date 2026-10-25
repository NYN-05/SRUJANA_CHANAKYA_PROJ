"""Echo code derivation and reply matching (INTEGRITY_SPEC section 7, I-08, FR-ECH-001)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .hashing import TypeByte, plain_hash, require_bytes, sha256

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32
_CODE_AFTER_CONFIRM = re.compile(r"(?<![0-9A-Z])CONFIRM ([0-9A-Z]{4})(?![0-9A-Z])")
_LOOKALIKES = str.maketrans({"O": "0", "I": "1", "L": "1"})


def recap_hash(content: dict[str, Any]) -> bytes:
    """H(0x21 || JCS(recap content)); the caller passes the hashed fields only, never the code line."""
    return plain_hash(TypeByte.RECAP, content)


def echo_code(recap_digest: bytes) -> str:
    """First 20 bits (big-endian) of H(0x50 || recap_hash) as four Crockford base32 characters."""
    digest = sha256(bytes([TypeByte.ECHO_CODE]) + require_bytes(recap_digest, 32, "recap hash"))
    bits = int.from_bytes(digest[:3], "big") >> 4
    return "".join(ALPHABET[(bits >> shift) & 0x1F] for shift in (15, 10, 5, 0))


def extract_code(reply: str) -> str | None:
    """NFC, upper-case, trim and collapse spaces; find CONFIRM, then map O→0, I/L→1 on the code token only (I-08)."""
    text = " ".join(unicodedata.normalize("NFC", reply).upper().split())
    match = _CODE_AFTER_CONFIRM.search(text)
    if not match:
        return None
    code = match.group(1).translate(_LOOKALIKES)
    return code if all(ch in ALPHABET for ch in code) else None


def codes_match(reply: str, code: str) -> bool:
    found = extract_code(reply)
    return found is not None and found == code
