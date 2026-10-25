"""SHA-256 with domain separation, text normalisation and RFC 8785 canonicalisation (INTEGRITY_SPEC 2 to 5).

Every operand is raw bytes; hex appears only at the edges (Q-59). No error falls back to a weaker hash.
"""

from __future__ import annotations

import hashlib
import math
import unicodedata
from enum import IntEnum
from typing import Any

import rfc8785

MAX_SAFE_INTEGER = 2**53 - 1


class CanonicalizationError(ValueError):
    """The object cannot be canonicalised (unsafe number, non-JSON type or non-string key)."""


class TypeByte(IntEnum):
    MERKLE_NODE = 0x01
    MESSAGE = 0x10
    VOICE_AUDIO = 0x11
    TRANSCRIPT_SPAN = 0x12
    HANDSHAKE_SEAL = 0x13
    ATTACHMENT = 0x14
    TERM = 0x15
    IMPORT_RECORD = 0x16
    TERMS_SET = 0x20
    RECAP = 0x21
    CONFIRMATION = 0x22
    CHAIN_LINK = 0x30
    RECEIPT = 0x40
    ECHO_CODE = 0x50


SALTED_TYPES = frozenset(
    {
        TypeByte.MESSAGE,
        TypeByte.VOICE_AUDIO,
        TypeByte.TRANSCRIPT_SPAN,
        TypeByte.HANDSHAKE_SEAL,
        TypeByte.ATTACHMENT,
        TypeByte.TERM,
        TypeByte.CONFIRMATION,
    }
)
PLAIN_TYPES = frozenset(
    {
        TypeByte.IMPORT_RECORD,
        TypeByte.TERMS_SET,
        TypeByte.RECAP,
        TypeByte.CHAIN_LINK,
        TypeByte.RECEIPT,
        TypeByte.ECHO_CODE,
    }
)


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def normalize_text(text: str) -> str:
    """Unicode NFC, then every CRLF and lone CR becomes LF. Nothing is trimmed or collapsed."""
    return unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")


def normalize_record(obj: Any) -> Any:
    """Return a copy with normalize_text applied to every string value; keys are never normalised."""
    if isinstance(obj, str):
        return normalize_text(obj)
    if isinstance(obj, dict):
        return {key: normalize_record(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [normalize_record(value) for value in obj]
    return obj


def _check_json(obj: Any) -> None:
    if obj is None or isinstance(obj, (bool, str)):
        return
    if isinstance(obj, int):
        if abs(obj) > MAX_SAFE_INTEGER:
            raise CanonicalizationError("integer outside the safe range ±(2^53 - 1)")
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            raise CanonicalizationError("NaN and infinities cannot be canonicalised")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                raise CanonicalizationError("object keys must be strings")
            _check_json(value)
    elif isinstance(obj, list):
        for value in obj:
            _check_json(value)
    else:
        raise CanonicalizationError(f"{type(obj).__name__} is not a JSON type")


def canonicalize(obj: Any) -> bytes:
    """Pure RFC 8785 (JCS) as UTF-8 bytes. It normalises nothing; see record_bytes."""
    _check_json(obj)
    try:
        return rfc8785.dumps(obj)
    except Exception as exc:  # the library's own domain errors
        raise CanonicalizationError(str(exc)) from exc


def record_bytes(obj: Any) -> bytes:
    """Canonical bytes of a record: normalize_text on string values, then JCS."""
    return canonicalize(normalize_record(obj))


def payload_digest_json(obj: Any) -> bytes:
    return sha256(record_bytes(obj))


def payload_digest_bytes(data: bytes) -> bytes:
    """Raw file bytes (audio, attachments, the export file) are hashed with no normalisation."""
    return sha256(data)


def require_bytes(value: Any, size: int, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)) or len(value) != size:
        raise ValueError(f"{name} must be {size} raw bytes")
    return bytes(value)


def _type_byte(type_byte: int, allowed: frozenset[TypeByte], form: str) -> bytes:
    if isinstance(type_byte, bool) or not isinstance(type_byte, int) or type_byte not in allowed:
        raise ValueError(f"type byte {type_byte!r} is not a {form} record type")
    return bytes([type_byte])


def leaf_hash(type_byte: int, salt: bytes, payload_digest: bytes) -> bytes:
    """leaf = H(type_byte || salt || payload_digest) for the salted types only."""
    prefix = _type_byte(type_byte, SALTED_TYPES, "salted")
    return sha256(prefix + require_bytes(salt, 16, "salt") + require_bytes(payload_digest, 32, "payload digest"))


def plain_hash(type_byte: int, obj: Any) -> bytes:
    """H(type_byte || JCS(normalised obj)) for the plain types only."""
    return sha256(_type_byte(type_byte, PLAIN_TYPES, "plain") + record_bytes(obj))
