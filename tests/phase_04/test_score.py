"""Phase 4: Evidence Strength score (FR-SCO-001, FR-SCO-002; I-06)."""

from __future__ import annotations

import pytest

from packages.contracts import TermState
from packages.intelligence.score import ScoreInput, compute_score

S, U, C, M = TermState.STATED, TermState.UNCLEAR, TermState.CONTRADICTED, TermState.MISSING
KEYS = ["parties", "scope", "quantity", "price", "advance", "delivery_date", "final_payment", "late_penalty"]


def inputs(overrides=None, default=(True, S, True)):
    out = []
    for k in KEYS:
        confirmed, state, ack = (overrides or {}).get(k, default)
        out.append(ScoreInput(key=k, confirmed=confirmed, state=state, acknowledged_by_both=ack))
    return out


WORKED = {
    "delivery_date": (False, U, False),
    "final_payment": (False, M, False),
    "late_penalty": (False, M, False),
}


def test_worked_example_is_55(supply_playbook):
    r = compute_score(inputs(WORKED), supply_playbook)
    assert r.score == 55


def test_breakdown_sums_to_score_and_lists_booleans(supply_playbook):
    r = compute_score(inputs(WORKED), supply_playbook)
    rows = {row.key: row for row in r.rows}
    assert set(rows) == set(KEYS)
    assert sum(row.points for row in r.rows) == 55
    assert (rows["price"].weight, rows["price"].present, rows["price"].clear, rows["price"].acknowledged, rows["price"].points) == (15, True, True, True, 15)
    assert (rows["delivery_date"].present, rows["delivery_date"].points) == (False, 0)
    assert (r.present_count, r.clear_count, r.acknowledged_count, r.total) == (5, 5, 5, 8)


def test_all_clear_and_acknowledged_is_100(supply_playbook):
    assert compute_score(inputs(), supply_playbook).score == 100


def test_no_terms_is_0(supply_playbook):
    assert compute_score([], supply_playbook).score == 0
    assert compute_score(inputs(default=(False, M, False)), supply_playbook).score == 0


def test_unconfirmed_terms_earn_nothing(supply_playbook):
    assert compute_score(inputs(default=(False, S, True)), supply_playbook).score == 0


def test_present_and_clear_without_ack_is_70_percent(supply_playbook):
    only_price = {k: (False, M, False) for k in KEYS if k != "price"}
    only_price["price"] = (True, S, False)
    r = compute_score(inputs(only_price), supply_playbook)
    assert r.score == 11  # 15 * 0.7 = 10.5, rounded half up (I-06)


def test_present_only_is_40_percent(supply_playbook):
    one = {k: (False, M, False) for k in KEYS if k != "delivery_date"}
    one["delivery_date"] = (True, U, False)
    assert compute_score(inputs(one), supply_playbook).score == 6  # 15 * 0.4


def test_ack_counts_only_when_present(supply_playbook):
    one = {k: (False, M, False) for k in KEYS if k != "price"}
    one["price"] = (False, S, True)
    assert compute_score(inputs(one), supply_playbook).score == 0


def test_conflict_is_present_but_not_clear(supply_playbook):
    one = {k: (False, M, False) for k in KEYS if k != "price"}
    one["price"] = (True, C, True)
    assert compute_score(inputs(one), supply_playbook).score == 11  # 15 * (0.4 + 0.3) = 10.5 -> 11


def test_rounding_uses_exact_decimals(supply_playbook):
    # 10 * 0.7 = 7.0 exactly; float arithmetic gives 6.999999999999999
    one = {k: (False, M, False) for k in KEYS if k != "advance"}
    one["advance"] = (True, S, False)
    assert compute_score(inputs(one), supply_playbook).score == 7


def test_non_required_terms_do_not_score(supply_playbook):
    base = compute_score(inputs(WORKED), supply_playbook).score
    extra = inputs(WORKED) + [ScoreInput(key="gst_status", confirmed=True, state=S, acknowledged_by_both=True)]
    assert compute_score(extra, supply_playbook).score == base


def test_unknown_keys_ignored(supply_playbook):
    extra = inputs(WORKED) + [ScoreInput(key="not_a_term", confirmed=True, state=S, acknowledged_by_both=True)]
    assert compute_score(extra, supply_playbook).score == 55


def test_freelance_weights(freelance_playbook):
    keys = [t.key for t in freelance_playbook.terms if t.required]
    half = [ScoreInput(key=k, confirmed=k in ("parties", "deliverable"), state=S, acknowledged_by_both=True) for k in keys]
    assert compute_score(half, freelance_playbook).score == 30


@pytest.mark.parametrize("n_confirmed", range(9))
def test_score_is_monotonic_in_confirmations(supply_playbook, n_confirmed):
    ov = {k: ((i < n_confirmed), S, True) for i, k in enumerate(KEYS)}
    more = {k: ((i < n_confirmed + 1), S, True) for i, k in enumerate(KEYS)}
    assert compute_score(inputs(more), supply_playbook).score >= compute_score(inputs(ov), supply_playbook).score
