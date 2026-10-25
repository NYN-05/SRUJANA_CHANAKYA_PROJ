"""Phase 7: receipts built by the vault (INTEGRITY_SPEC section 9; I-09; S8)."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue
from packages.integrity.hashing import TypeByte, plain_hash
from packages.integrity.merkle import merkle_root
from packages.integrity.receipt import SPEC_VERSION, receipt_hash
from packages.integrity.timestamp import parse_timestamp

BODY_FIELDS = {"spec_version", "deal_id", "leaf_count", "root", "chain", "recorded_at", "anchor", "import_record_hash"}


@pytest.fixture
def deal(vault):
    deal_id, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal_id)
    vault.create_version(deal_id)
    vault.correct_term(deal_id, "delivery_date", DateValue(date="2026-11-15"))
    vault.create_version(deal_id)
    return deal_id


def test_body_fields_and_hash(vault, deal):
    r = vault.build_receipt(deal)
    assert set(r.body) == BODY_FIELDS
    assert r.body["spec_version"] == SPEC_VERSION
    assert r.receipt_hash == receipt_hash(r.body)


def test_root_and_leaf_count_cover_every_leaf(vault, deal):
    r = vault.build_receipt(deal)
    leaves = vault.leaves(deal)
    assert r.body["leaf_count"] == len(leaves)
    assert r.body["root"] == merkle_root([l.leaf_hash for l in leaves]).hex()


def test_chain_lists_every_version(vault, deal):
    r = vault.build_receipt(deal)
    versions = vault.versions(deal)
    assert [c["version_n"] for c in r.body["chain"]] == [1, 2]
    for entry, v in zip(r.body["chain"], versions):
        assert entry == {"version_n": v.n, "terms_digest": v.terms_digest.hex(), "root": v.root.hex(), "link": v.link.hex()}


def test_import_record_hash(vault, deal):
    rec = vault.import_record(deal)
    r = vault.build_receipt(deal)
    assert r.body["import_record_hash"] == plain_hash(TypeByte.IMPORT_RECORD, rec.model_dump(mode="json")).hex()


def test_recorded_at_is_device_clock_with_offset(vault, deal):
    r = vault.build_receipt(deal)
    assert parse_timestamp(r.body["recorded_at"]).utcoffset() is not None
    assert r.body["anchor"] is None


def test_version_records_the_leaf_count_its_root_covers(vault, deal):
    first, second = vault.versions(deal)
    leaves = [l.leaf_hash for l in vault.leaves(deal)]
    assert merkle_root(leaves[: first.leaf_count]) == first.root
    assert merkle_root(leaves[: second.leaf_count]) == second.root
    assert first.leaf_count < second.leaf_count == len(leaves)


def test_receipt_before_any_version_has_an_empty_chain(vault):
    deal_id, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    assert vault.build_receipt(deal_id).body["chain"] == []


def test_receipts_are_stored(vault, deal):
    a = vault.build_receipt(deal)
    assert vault.audit_events(deal)[-1].action in {"receipt", "export"}
    b = vault.build_receipt(deal)
    assert a.body["root"] == b.body["root"]
