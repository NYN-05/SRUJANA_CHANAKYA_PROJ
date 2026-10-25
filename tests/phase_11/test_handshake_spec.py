"""Phase 11b (deferred, R-02): Blind Handshake lite. FR-HSK-001 to 007, ADR-019."""

from __future__ import annotations

import pytest
from helpers import commit_sample

pytestmark = pytest.mark.deferred

ANSWERS_RAJU = {"delivery_date": "2026-11-15", "final_payment": "on delivery", "late_penalty": "none", "price": "480 each"}
ANSWERS_MEENA = {"delivery_date": "2026-11-22", "final_payment": "30 days after delivery", "late_penalty": "none", "price": "480 each"}


@pytest.fixture
def deal(vault):
    return commit_sample(vault, "ambiguous.txt", "Raju", "Meena")[0]


def test_questions_come_from_playbook(vault, deal, supply_playbook):
    hs = vault.handshake_start(deal, mode="reply")
    assert hs.questions == list(supply_playbook.handshake_questions)
    assert hs.state == "asking"


def test_second_set_refused_before_first_is_sealed(vault, deal):
    from packages.vault import HandshakeOrderError

    vault.handshake_start(deal, mode="handover")
    with pytest.raises(HandshakeOrderError):
        vault.handshake_submit(deal, order=2, answers=ANSWERS_MEENA)
    assert vault.handshake_answers(deal) == []
    assert vault.audit_events(deal)[-1].action == "seal_refused"


def test_seal_order_and_later_timestamp(vault, deal):
    vault.handshake_start(deal, mode="handover")
    s1 = vault.handshake_submit(deal, order=1, answers=ANSWERS_RAJU)
    s2 = vault.handshake_submit(deal, order=2, answers=ANSWERS_MEENA)
    assert s2.sealed_at >= s1.sealed_at and len(s1.seal_hash) == 32
    assert vault.handshake_state(deal) == "both_sealed"


def test_first_answers_hidden_until_both_sealed(vault, deal):
    vault.handshake_start(deal, mode="handover")
    vault.handshake_submit(deal, order=1, answers=ANSWERS_RAJU)
    with pytest.raises(PermissionError):
        vault.handshake_reveal(deal)


def test_reveal_describes_differences(vault, deal):
    vault.handshake_start(deal, mode="handover")
    vault.handshake_submit(deal, order=1, answers=ANSWERS_RAJU)
    vault.handshake_submit(deal, order=2, answers=ANSWERS_MEENA)
    rows = {r.term_key: r for r in vault.handshake_reveal(deal)}
    assert rows["delivery_date"].result == "⚠ Mismatch" and rows["delivery_date"].difference == "7 days apart"
    assert rows["price"].result == "✓ Match"


def test_skip_falls_back_to_plain_recap(vault, deal):
    vault.handshake_start(deal, mode="reply")
    vault.handshake_skip(deal)
    assert vault.handshake_state(deal) == "fallback_recap"


def test_reply_mode_label_states_its_limit(vault, deal):
    hs = vault.handshake_start(deal, mode="reply")
    assert hs.mode_note == "You saw the other side's reply in WhatsApp before pasting it. Your own answers were sealed first."
