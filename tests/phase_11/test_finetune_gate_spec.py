"""Phase 11e (deferred, R-03): the fine-tuning gate of ADR-023 / FR-FTN-001. Gate values are TBD (Q-50)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.deferred

BASE = {"f1": 0.80, "grounding_failures": 3, "injection_changed": 0, "needs_review_rate": 0.10, "slices": {"en": 0.85, "hinglish": 0.75}}


def decide(tuned, **kw):
    from eval.runner.finetune_gate import gate

    return gate(BASE, tuned, margin=0.03, tolerance=0.01, **kw)


def test_ships_only_when_it_beats_base_by_margin():
    better = dict(BASE, f1=0.84, slices={"en": 0.86, "hinglish": 0.80})
    assert decide(better).ship is True
    assert decide(dict(better, f1=0.82)).ship is False


def test_any_safety_regression_blocks():
    better = dict(BASE, f1=0.90, slices={"en": 0.9, "hinglish": 0.9})
    assert decide(dict(better, injection_changed=1)).ship is False
    assert decide(dict(better, grounding_failures=4)).ship is False
    assert decide(dict(better, needs_review_rate=0.2)).ship is False


def test_language_slice_regression_blocks():
    assert decide(dict(BASE, f1=0.9, slices={"en": 0.95, "hinglish": 0.70})).ship is False


def test_training_data_must_exclude_eval_chats():
    better = dict(BASE, f1=0.9, slices={"en": 0.9, "hinglish": 0.9})
    assert decide(better, training_ids={"chat-001"}, eval_ids={"chat-001", "chat-002"}).ship is False


def test_no_claim_when_gate_fails():
    result = decide(BASE)
    assert result.ship is False and result.claim_allowed is False
