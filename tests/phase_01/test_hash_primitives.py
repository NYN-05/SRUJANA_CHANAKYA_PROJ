"""Phase 1: SHA-256, domain separation, salted leaves and plain hashes (INTEGRITY_SPEC 2, 3, 5)."""

from __future__ import annotations

import hashlib

import pytest

from packages.integrity.hashing import (
    PLAIN_TYPES,
    SALTED_TYPES,
    TypeByte,
    leaf_hash,
    payload_digest_bytes,
    payload_digest_json,
    plain_hash,
    record_bytes,
    sha256,
)


def H(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


EXPECTED_BYTES = {
    "MERKLE_NODE": 0x01,
    "MESSAGE": 0x10,
    "VOICE_AUDIO": 0x11,
    "TRANSCRIPT_SPAN": 0x12,
    "HANDSHAKE_SEAL": 0x13,
    "ATTACHMENT": 0x14,
    "TERM": 0x15,
    "IMPORT_RECORD": 0x16,
    "TERMS_SET": 0x20,
    "RECAP": 0x21,
    "CONFIRMATION": 0x22,
    "CHAIN_LINK": 0x30,
    "RECEIPT": 0x40,
    "ECHO_CODE": 0x50,
}


def test_sha256_known_answer():
    assert sha256(b"abc").hex() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert len(sha256(b"")) == 32


@pytest.mark.parametrize("name,value", sorted(EXPECTED_BYTES.items()))
def test_type_byte_values(name, value):
    assert TypeByte[name] == value


def test_zero_byte_is_reserved():
    assert 0x00 not in {int(t) for t in TypeByte}


def test_salted_and_plain_sets_match_spec():
    salted = {0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x22}
    plain = {0x16, 0x20, 0x21, 0x30, 0x40, 0x50}
    assert {int(t) for t in SALTED_TYPES} == salted
    assert {int(t) for t in PLAIN_TYPES} == plain


def test_leaf_formula():
    salt = bytes([7]) * 16
    digest = H(b"payload")
    expected = H(bytes([0x10]) + salt + digest)
    assert leaf_hash(TypeByte.MESSAGE, salt, digest) == expected


def test_payload_digest_json_uses_normalised_jcs():
    obj = {"b": "é", "a": 1}
    assert record_bytes(obj) == '{"a":1,"b":"é"}'.encode("utf-8")
    assert payload_digest_json(obj) == H('{"a":1,"b":"é"}'.encode("utf-8"))


def test_payload_digest_bytes_is_raw_sha256():
    data = b"\x00\x01binary\xff"
    assert payload_digest_bytes(data) == H(data)


def test_plain_hash_formula():
    obj = {"deal_id": "d1", "version_n": 1}
    expected = H(bytes([0x20]) + b'{"deal_id":"d1","version_n":1}')
    assert plain_hash(TypeByte.TERMS_SET, obj) == expected


@pytest.mark.parametrize("bad_salt", [b"", bytes(15), bytes(17), bytes(32)])
def test_leaf_rejects_wrong_salt_size(bad_salt):
    with pytest.raises(ValueError):
        leaf_hash(TypeByte.MESSAGE, bad_salt, H(b"x"))


@pytest.mark.parametrize("bad_digest", [b"", bytes(31), bytes(33), H(b"x").hex().encode()])
def test_leaf_rejects_wrong_digest_size(bad_digest):
    with pytest.raises(ValueError):
        leaf_hash(TypeByte.MESSAGE, bytes(16), bad_digest)


@pytest.mark.parametrize("plain_type", [TypeByte.RECAP, TypeByte.RECEIPT, TypeByte.CHAIN_LINK, 0x00, 0x99])
def test_leaf_rejects_non_salted_types(plain_type):
    with pytest.raises(ValueError):
        leaf_hash(plain_type, bytes(16), H(b"x"))


@pytest.mark.parametrize("salted_type", [TypeByte.MESSAGE, TypeByte.CONFIRMATION, 0x00, 0x99])
def test_plain_rejects_salted_or_unknown_types(salted_type):
    with pytest.raises(ValueError):
        plain_hash(salted_type, {"a": 1})


def test_domain_separation_changes_hash():
    salt, digest = bytes(16), H(b"same")
    assert leaf_hash(TypeByte.MESSAGE, salt, digest) != leaf_hash(TypeByte.TERM, salt, digest)
    assert plain_hash(TypeByte.TERMS_SET, {"a": 1}) != plain_hash(TypeByte.RECAP, {"a": 1})


def test_salt_changes_leaf():
    digest = H(b"same")
    assert leaf_hash(TypeByte.MESSAGE, bytes(16), digest) != leaf_hash(TypeByte.MESSAGE, bytes([1]) * 16, digest)
