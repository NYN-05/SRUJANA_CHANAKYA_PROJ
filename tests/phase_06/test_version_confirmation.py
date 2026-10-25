"""Phase 6: a version is confirmed only when both parties are (FR-ECH-003; S6, S7)."""

from __future__ import annotations

from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue
from packages.ingest.recap import build_recap


def _recap(vault, deal, playbook):
    v = vault.create_version(deal)
    draft = build_recap(vault.agreed_terms(deal), playbook, "en", "Meena", deal_id=deal, version_n=v.n)
    return v, vault.create_recap(deal, v.n, draft)


def test_both_parties_needed(vault, supply_playbook):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    v, recap = _recap(vault, deal, supply_playbook)
    assert vault.version_confirmed(deal, v.n) is False
    vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}", sender="Meena")
    assert vault.version_confirmed(deal, v.n) is False, "the user's own approval is still missing"
    vault.approve_recap(recap.id)
    assert vault.version_confirmed(deal, v.n) is True


def test_approve_alone_is_not_enough(vault, supply_playbook):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    v, recap = _recap(vault, deal, supply_playbook)
    vault.approve_recap(recap.id)
    assert vault.version_confirmed(deal, v.n) is False


def test_confirmation_does_not_carry_to_next_version(vault, supply_playbook):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    v1, recap = _recap(vault, deal, supply_playbook)
    vault.approve_recap(recap.id)
    vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}", sender="Meena")
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    v2, _ = _recap(vault, deal, supply_playbook)
    assert vault.version_confirmed(deal, v1.n) is True
    assert vault.version_confirmed(deal, v2.n) is False


def test_acknowledgement_after_confirmed_recap(vault, supply_playbook):
    # FR-SCO-001: a confirmed recap containing a term counts as acknowledged by both
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    _, recap = _recap(vault, deal, supply_playbook)
    vault.approve_recap(recap.id)
    vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}", sender="Meena")
    assert vault.agreed_terms(deal)["delivery_date"].acknowledged_by_other is True
