"""Precision, recall and F1 per term key (EVALUATION section 3). Used by Phases 8 and 10 as well."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def precision_recall_f1(gold: Mapping[str, Any], proposed: Mapping[str, Any]) -> dict[str, Any]:
    """Compare normalised term values by key.

    ``gold`` maps a key to its true value, or to None when the term is missing in the chat; ``proposed`` maps
    the keys a system proposed to their values. A proposal counts as correct when it equals the gold value.
    Missing gold terms do not count for recall, and a value proposed for one hurts precision.
    """
    expected = {k: v for k, v in gold.items() if v is not None}
    correct = {k for k, v in proposed.items() if k in expected and expected[k] == v}
    precision = len(correct) / len(proposed) if proposed else 0.0
    recall = len(correct) / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    per_key = {
        k: {"gold": gold.get(k), "proposed": proposed.get(k), "correct": gold.get(k) == proposed.get(k)}
        for k in sorted({*gold, *proposed})
    }
    return {"precision": precision, "recall": recall, "f1": f1, "per_key": per_key}


def ai_contribution(gold: Mapping[str, Any], rules_only: Mapping[str, Any], rules_and_ai: Mapping[str, Any]) -> dict[str, Any]:
    """What the model adds (AI_SPEC section 10): the scores of the rules alone, of rules plus model, and the difference.
    The trust report prints it; a model that does not improve on the rules does not ship in the default tier."""
    before, after = precision_recall_f1(gold, rules_only), precision_recall_f1(gold, rules_and_ai)
    return {
        "rules_only": before,
        "rules_and_ai": after,
        "delta": {name: after[name] - before[name] for name in ("precision", "recall", "f1")},
    }
