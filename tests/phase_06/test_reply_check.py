"""Phase 6: checking the counterparty's pasted reply (FR-ECH-002 to 004; I-08; THREAT_MODEL T5, T6)."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import ConfirmationState, DateValue
from packages.ingest.recap import build_recap
from packages.integrity.echo import ALPHABET
from packages.integrity.hashing import TypeByte

NOT_CONFIRMED = ConfirmationState.NOT_CONFIRMED


@pytest.fixture
def setup(vault, supply_playbook):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    v = vault.create_version(deal)
    draft = build_recap(vault.agreed_terms(deal), supply_playbook, "en", "Meena", deal_id=deal, version_n=v.n)
    recap = vault.create_recap(deal, v.n, draft)
    return deal, recap


def wrong_code(code):
    return code[:3] + next(ch for ch in ALPHABET if ch != code[3])


def confirmation_leaves(vault, deal):
    return [l for l in vault.leaves(deal) if l.type_byte == TypeByte.CONFIRMATION]


def test_lower_case_reply_with_header_confirms(vault, setup):
    deal, recap = setup
    res = vault.check_reply(recap.id, f"24/10/26, 11:50 - Meena: confirm {recap.echo_code.lower()}")
    assert res.state == ConfirmationState.CONFIRMED and res.failure_reason is None
    assert res.sender_entered_by_user is False


def test_reply_without_header_needs_sender_and_is_marked(vault, setup):
    deal, recap = setup
    res = vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}", sender="Meena")
    assert res.state == ConfirmationState.CONFIRMED
    assert res.sender_entered_by_user is True


def test_reply_without_header_or_sender_refused(vault, setup):
    _, recap = setup
    with pytest.raises(ValueError):
        vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}")


def test_words_around_the_code_are_ignored(vault, setup):
    _, recap = setup
    res = vault.check_reply(recap.id, f"ok confirm {recap.echo_code} thanks", sender="Meena")
    assert res.state == ConfirmationState.CONFIRMED


def test_wrong_code(vault, setup):
    _, recap = setup
    res = vault.check_reply(recap.id, f"CONFIRM {wrong_code(recap.echo_code)}", sender="Meena")
    assert (res.state, res.failure_reason) == (NOT_CONFIRMED, "code_mismatch")
    assert res.message_en == "code does not match this recap"


def test_no_code(vault, setup):
    _, recap = setup
    res = vault.check_reply(recap.id, "haan sab theek hai", sender="Meena")
    assert (res.state, res.failure_reason) == (NOT_CONFIRMED, "no_code")
    assert res.message_en == "We could not find a CONFIRM code in this reply."


def test_wrong_sender(vault, setup):
    _, recap = setup
    res = vault.check_reply(recap.id, f"24/10/26, 11:50 - Raju: CONFIRM {recap.echo_code}")
    assert (res.state, res.failure_reason) == (NOT_CONFIRMED, "wrong_sender")
    assert res.message_en == "sender is not the other party"


def test_stale_code_after_new_version(vault, setup, supply_playbook):
    deal, recap1 = setup
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-22"))
    v2 = vault.create_version(deal)
    draft = build_recap(vault.agreed_terms(deal), supply_playbook, "en", "Meena", deal_id=deal, version_n=v2.n)
    recap2 = vault.create_recap(deal, v2.n, draft)
    res = vault.check_reply(recap2.id, f"CONFIRM {recap1.echo_code}", sender="Meena")
    assert (res.state, res.failure_reason) == (NOT_CONFIRMED, "stale_code")
    assert res.message_en == "this code is for an older version"
    old = vault.check_reply(recap1.id, f"CONFIRM {recap1.echo_code}", sender="Meena")
    assert old.failure_reason == "stale_code", "an older recap can never be confirmed once a newer one exists"


def test_leaf_only_on_success(vault, setup):
    deal, recap = setup
    before = len(confirmation_leaves(vault, deal))
    vault.check_reply(recap.id, "CONFIRM ZZZZ", sender="Meena")
    assert len(confirmation_leaves(vault, deal)) == before
    vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}", sender="Meena")
    leaves = confirmation_leaves(vault, deal)
    assert len(leaves) == before + 1
    assert set(leaves[-1].payload) == {"deal_id", "version_n", "party_id", "reply_text", "reply_ts", "code", "sender_entered_by_user"}


def test_failed_attempts_are_recorded(vault, setup):
    _, recap = setup
    vault.check_reply(recap.id, "CONFIRM ZZZZ", sender="Meena")
    states = [c.state for c in vault.confirmations(recap.id)]
    assert NOT_CONFIRMED in states


def test_multi_line_paste_uses_last_counterparty_confirm(vault, setup):
    _, recap = setup
    paste = (
        "24/10/26, 11:48 - Raju: please check\n"
        f"24/10/26, 11:49 - Meena: CONFIRM {wrong_code(recap.echo_code)}\n"
        f"24/10/26, 11:50 - Meena: sorry typo, CONFIRM {recap.echo_code}\n"
    )
    assert vault.check_reply(recap.id, paste).state == ConfirmationState.CONFIRMED


def test_check_reply_is_audited(vault, setup):
    deal, recap = setup
    vault.check_reply(recap.id, f"CONFIRM {recap.echo_code}", sender="Meena")
    assert vault.audit_events(deal)[-1].action == "check_reply"
