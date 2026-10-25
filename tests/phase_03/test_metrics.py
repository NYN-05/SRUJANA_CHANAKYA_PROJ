"""Phase 3: precision, recall and F1 helper used by the trust report (EVALUATION section 3)."""

from __future__ import annotations

import pytest

from eval.runner.metrics import precision_recall_f1


def test_perfect():
    gold = {"price": "48000", "quantity": "200"}
    r = precision_recall_f1(gold, dict(gold))
    assert (r["precision"], r["recall"], r["f1"]) == (1.0, 1.0, 1.0)


def test_half_right():
    gold = {"price": "48000", "quantity": "200"}
    r = precision_recall_f1(gold, {"price": "48000", "quantity": "100"})
    assert r["precision"] == pytest.approx(0.5)
    assert r["recall"] == pytest.approx(0.5)
    assert r["f1"] == pytest.approx(0.5)


def test_missing_gold_values_do_not_count_for_recall():
    gold = {"price": "48000", "late_penalty": None}
    r = precision_recall_f1(gold, {"price": "48000"})
    assert r["recall"] == 1.0


def test_proposing_a_value_for_missing_gold_hurts_precision():
    gold = {"price": "48000", "late_penalty": None}
    r = precision_recall_f1(gold, {"price": "48000", "late_penalty": "500 per day"})
    assert r["precision"] == pytest.approx(0.5)


def test_nothing_proposed():
    r = precision_recall_f1({"price": "48000"}, {})
    assert (r["precision"], r["recall"], r["f1"]) == (0.0, 0.0, 0.0)


def test_per_key_breakdown():
    r = precision_recall_f1({"price": "1", "quantity": "2"}, {"price": "1", "quantity": "3"})
    assert r["per_key"]["price"]["correct"] is True
    assert r["per_key"]["quantity"]["correct"] is False
