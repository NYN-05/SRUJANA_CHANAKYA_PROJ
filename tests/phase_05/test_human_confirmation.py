"""Phase 5: the only path into the record is a human action (FR-EXT-005, FR-EXT-006, ADR-007)."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue, MoneyValue, Origin, TermState
from packages.vault import TermNotConfirmable


@pytest.fixture
def deal(vault):
    deal_id, draft = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    return deal_id


def test_proposals_are_not_agreed(vault, deal):
    assert vault.agreed_terms(deal) == {}
    assert vault.proposals(deal)["price"].state == TermState.STATED


def test_confirm_stated_term_as_is(vault, deal):
    agreed = vault.confirm_term(deal, "price")
    assert agreed.value == MoneyValue(paise="48000", per="item")
    assert agreed.sources and agreed.confirmed_by == "me"
    assert agreed.origin == Origin.RULES
    assert "price" in vault.agreed_terms(deal)


def test_unclear_term_needs_an_explicit_value(vault, deal):
    with pytest.raises(TermNotConfirmable):
        vault.confirm_term(deal, "delivery_date")


def test_missing_term_needs_an_explicit_value(vault, deal):
    with pytest.raises(TermNotConfirmable):
        vault.confirm_term(deal, "final_payment")


def test_correction_makes_term_clear_with_user_origin_and_audit(vault, deal):
    before = len(vault.audit_events(deal))
    agreed = vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    assert agreed.value == DateValue(date="2026-11-15")
    assert agreed.origin == Origin.USER
    assert agreed.sources, "a corrected term keeps its original source"
    events = vault.audit_events(deal)
    assert len(events) == before + 1
    ev = events[-1]
    assert ev.action == "correct_term" and ev.detail["key"] == "delivery_date"
    assert "old" in ev.detail and ev.detail["new"] == {"kind": "date", "date": "2026-11-15"}


def test_confirm_writes_audit_row(vault, deal):
    vault.confirm_term(deal, "price")
    assert vault.audit_events(deal)[-1].action == "confirm_term"


def test_reject_removes_from_agreed_and_audits(vault, deal):
    vault.confirm_term(deal, "price")
    vault.reject_term(deal, "price")
    assert "price" not in vault.agreed_terms(deal)
    assert vault.audit_events(deal)[-1].action == "reject_term"


def test_conflict_needs_a_chosen_value(vault):
    deal, _ = commit_sample(vault, "contradictory.txt", "Patel", "Sai")
    with pytest.raises(TermNotConfirmable):
        vault.confirm_term(deal, "price")
    agreed = vault.confirm_term(deal, "price", MoneyValue(paise="4500000", per="total"))
    assert agreed.value.paise == "4500000"


def test_unknown_key_refused(vault, deal):
    with pytest.raises(KeyError):
        vault.confirm_term(deal, "not_a_term")


def test_new_proposals_do_not_overwrite_confirmed_terms(vault, deal, supply_playbook):
    vault.confirm_term(deal, "price")
    proposals = list(vault.proposals(deal).values())
    changed = [p.model_copy(update={"value": MoneyValue(paise="1", per="item")}) if p.key == "price" else p for p in proposals]
    vault.save_proposals(deal, changed)
    assert vault.agreed_terms(deal)["price"].value.paise == "48000"


def test_audit_detail_holds_no_message_text(vault, deal):
    confirm_clear_terms(vault, deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    for ev in vault.audit_events(deal):
        flat = str(ev.detail)
        assert "will message when ready" not in flat and "ok. delivery next week" not in flat


def test_acknowledge_records_flag(vault, deal):
    vault.confirm_term(deal, "price")
    vault.acknowledge(deal, "price")
    assert vault.agreed_terms(deal)["price"].acknowledged_by_other is True
