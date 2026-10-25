"""Phase 5: versions supersede, never edit (FR-VER-001 to 003, FR-VLT-002, FR-VLT-003)."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue
from packages.integrity.chain import chain_link, terms_digest
from packages.integrity.hashing import TypeByte
from packages.integrity.merkle import merkle_root
from packages.vault import NothingToVersion


@pytest.fixture
def deal(vault):
    deal_id, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal_id)
    vault.correct_term(deal_id, "delivery_date", DateValue(date="2026-11-08"))
    return deal_id


def test_version_one(vault, deal):
    v1 = vault.create_version(deal)
    assert v1.n == 1 and v1.prev_link is None
    assert v1.terms_digest == terms_digest(v1.terms_set)
    assert v1.link == chain_link(None, v1.terms_digest, v1.root)
    assert v1.root == merkle_root([l.leaf_hash for l in vault.leaves(deal)])


def test_terms_set_shape(vault, deal):
    v1 = vault.create_version(deal)
    ts = v1.terms_set
    assert set(ts) == {"deal_id", "version_n", "playbook", "terms"}
    assert ts["version_n"] == 1 and ts["playbook"]["key"] == "supply_order"
    keys = [t["key"] for t in ts["terms"]]
    assert keys == sorted(keys), "terms sorted by key (INTEGRITY_SPEC 4.2)"
    assert set(keys) == {"parties", "scope", "quantity", "price", "advance", "delivery_date"}
    assert "final_payment" not in keys, "unconfirmed terms are never versioned"


def test_one_term_leaf_per_confirmed_term(vault, deal):
    before = len(vault.leaves(deal))
    vault.create_version(deal)
    new = vault.leaves(deal)[before:]
    assert [l.type_byte for l in new] == [TypeByte.TERM] * 6


def test_version_two_chains_and_v1_unchanged(vault, deal):
    v1 = vault.create_version(deal)
    snapshot = vault.versions(deal)[0]
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    v2 = vault.create_version(deal)
    assert v2.n == 2 and v2.prev_link == v1.link
    assert v2.link == chain_link(v1.link, v2.terms_digest, v2.root)
    assert vault.versions(deal)[0] == snapshot


def test_diff_shows_only_the_change(vault, deal):
    vault.create_version(deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    vault.create_version(deal)
    rows = {r.key: r for r in vault.diff_versions(deal, 1, 2)}
    assert rows["delivery_date"].change == "changed"
    assert rows["delivery_date"].a_value == DateValue(date="2026-11-08")
    assert rows["delivery_date"].b_value == DateValue(date="2026-11-15")
    assert {k for k, r in rows.items() if r.change != "no_change"} == {"delivery_date"}
    assert "price" in rows, "unchanged rows stay visible"


def test_diff_added_and_removed(vault, deal):
    from packages.contracts import TextValue

    vault.create_version(deal)
    vault.correct_term(deal, "late_penalty", TextValue(text="₹500 per day"))
    vault.reject_term(deal, "scope")
    vault.create_version(deal)
    rows = {r.key: r.change for r in vault.diff_versions(deal, 1, 2)}
    assert rows["late_penalty"] == "added" and rows["scope"] == "removed"


def test_reason_message_is_linked(vault, deal):
    msg = vault.messages(deal)[4]
    vault.create_version(deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    v2 = vault.create_version(deal, reason_message_id=msg.id)
    assert v2.reason_message_id == msg.id


def test_reason_must_be_a_message_of_this_deal(vault, deal):
    with pytest.raises((KeyError, ValueError)):
        vault.create_version(deal, reason_message_id="not-a-message")


def test_nothing_confirmed_refused(vault):
    deal_id, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    with pytest.raises(NothingToVersion):
        vault.create_version(deal_id)


def test_version_writes_audit(vault, deal):
    vault.create_version(deal)
    assert vault.audit_events(deal)[-1].action == "create_version"
