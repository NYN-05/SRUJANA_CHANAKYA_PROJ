"""Phase 4: choosing the gap the next message should close (FR-SUG-001; I-05)."""

from __future__ import annotations

from decimal import Decimal

from packages.contracts import TermState
from packages.intelligence.score import ScoreInput
from packages.intelligence.suggest import choose_targets, rank_gaps

S, U, C, M = TermState.STATED, TermState.UNCLEAR, TermState.CONTRADICTED, TermState.MISSING
KEYS = ["parties", "scope", "quantity", "price", "advance", "delivery_date", "final_payment", "late_penalty"]


def inputs(overrides):
    out = []
    for k in KEYS:
        confirmed, state, ack = overrides.get(k, (True, S, True))
        out.append(ScoreInput(key=k, confirmed=confirmed, state=state, acknowledged_by_both=ack))
    return out


RAJU_MEENA = {"delivery_date": (False, U, False), "final_payment": (False, M, False), "late_penalty": (False, M, False)}


def test_raju_meena_gains_and_order(supply_playbook):
    ranked = rank_gaps(inputs(RAJU_MEENA), supply_playbook)
    assert ranked == [("delivery_date", Decimal("15")), ("final_payment", Decimal("15")), ("late_penalty", Decimal("15"))]


def test_raju_meena_targets_delivery_and_final_payment(supply_playbook):
    assert choose_targets(inputs(RAJU_MEENA), supply_playbook) == ["delivery_date", "final_payment"]


def test_conflict_goes_first(supply_playbook):
    ov = dict(RAJU_MEENA, price=(False, C, False))
    assert rank_gaps(inputs(ov), supply_playbook)[0][0] == "price"
    assert choose_targets(inputs(ov), supply_playbook) == ["price"]  # price pairs with nothing


def test_higher_gain_beats_ask_order(supply_playbook):
    # delivery present and clear but not acknowledged: gain 15 * 0.3 = 4.5; final payment missing: gain 15
    ov = {"delivery_date": (True, S, False), "final_payment": (False, M, False)}
    ranked = rank_gaps(inputs(ov), supply_playbook)
    assert ranked[0] == ("final_payment", Decimal("15"))
    assert ranked[1] == ("delivery_date", Decimal("4.5"))


def test_partner_added_only_if_it_is_a_candidate(supply_playbook):
    ov = {"delivery_date": (False, U, False)}
    assert choose_targets(inputs(ov), supply_playbook) == ["delivery_date"]


def test_nothing_to_suggest_when_complete(supply_playbook):
    assert rank_gaps(inputs({}), supply_playbook) == []
    assert choose_targets(inputs({}), supply_playbook) == []


def test_never_more_than_two_targets(supply_playbook):
    everything_missing = {k: (False, M, False) for k in KEYS}
    assert 1 <= len(choose_targets(inputs(everything_missing), supply_playbook)) <= 2


def test_non_required_terms_never_targeted(supply_playbook):
    extra = inputs({}) + [ScoreInput(key="gst_status", confirmed=False, state=M, acknowledged_by_both=False)]
    assert choose_targets(extra, supply_playbook) == []
