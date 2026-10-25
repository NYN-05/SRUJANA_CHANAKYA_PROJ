"""Phase 4: acknowledgement detection (FR-FLG-005)."""

from __future__ import annotations

import pytest
from helpers import RAJU_MEENA, make_messages, rules_terms

from packages.intelligence.ack import acknowledged_keys


def acked(rows, playbook, **kw):
    msgs = make_messages(rows)
    terms = list(rules_terms(msgs, playbook).values())
    return acknowledged_keys(terms, msgs, me_id="Raju", counterparty_id="Meena", **kw)


def test_raju_meena(supply_playbook):
    assert acked(RAJU_MEENA, supply_playbook) == {"parties", "scope", "quantity", "price", "advance"}


@pytest.mark.parametrize("reply", ["ok", "Okay", "done", "yes", "haan", "ha", "theek hai", "thik hai", "agreed", "confirmed", "sure", "👍", "ok 👍"])
def test_agreement_words(supply_playbook, reply):
    keys = acked([("Raju", "200 shirts, 480 each"), ("Meena", reply)], supply_playbook)
    assert "price" in keys


@pytest.mark.parametrize("reply", ["no", "not ok", "too costly", "nahi", "let me think"])
def test_non_agreement(supply_playbook, reply):
    keys = acked([("Raju", "200 shirts, 480 each"), ("Meena", reply)], supply_playbook)
    assert "price" not in keys


def test_same_sender_is_not_acknowledgement(supply_playbook):
    keys = acked([("Raju", "200 shirts, 480 each"), ("Raju", "ok")], supply_playbook)
    assert "price" not in keys


def test_payment_confirmation_with_same_amount_acknowledges(supply_playbook):
    keys = acked([("Raju", "200 shirts, 480 each"), ("Meena", "ok"), ("Raju", "advance 48,000 please"), ("Meena", "sent 48000")], supply_playbook)
    assert "advance" in keys


def test_window_limits_acknowledgement(supply_playbook):
    rows = [("Raju", "200 shirts, 480 each")] + [("Raju", f"note {i}") for i in range(5)] + [("Meena", "ok")]
    assert "price" not in acked(rows, supply_playbook, window=5)
    assert "price" in acked(rows, supply_playbook, window=6)


def test_parties_need_both_people_in_chat(supply_playbook):
    assert "parties" not in acked([("Raju", "200 shirts, 480 each")], supply_playbook)
