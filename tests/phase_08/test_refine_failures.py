"""Phase 8: every model failure falls back to the rules result (Architecture section 11; AC-8.5)."""

from __future__ import annotations

import logging
import time

import pytest
from helpers import RAJU_MEENA, make_messages, rules_terms

from packages.intelligence.model.fake import FakeModelRunner
from packages.intelligence.model.refine import refine_terms


def setup(playbook):
    msgs = make_messages(RAJU_MEENA)
    return msgs, list(rules_terms(msgs, playbook).values())


def test_timeout_returns_rules_quickly(supply_playbook):
    msgs, rules = setup(supply_playbook)
    runner = FakeModelRunner('{"terms": []}', delay_s=3.0)
    start = time.perf_counter()
    result = refine_terms(rules, msgs, supply_playbook, runner, timeout_s=0.2, me_id="Raju", counterparty_id="Meena")
    assert time.perf_counter() - start < 1.5
    assert result.error == "timeout" and result.terms == rules


@pytest.mark.parametrize("exc", [RuntimeError("boom"), MemoryError(), OSError("model file vanished")])
def test_runner_exception(supply_playbook, exc):
    msgs, rules = setup(supply_playbook)
    result = refine_terms(rules, msgs, supply_playbook, FakeModelRunner("", error=exc), timeout_s=2, me_id="Raju", counterparty_id="Meena")
    assert result.error == "runner_error" and result.terms == rules


def test_invalid_output(supply_playbook):
    msgs, rules = setup(supply_playbook)
    result = refine_terms(rules, msgs, supply_playbook, FakeModelRunner("Sure! Here are the terms: price is 480."), timeout_s=2, me_id="Raju", counterparty_id="Meena")
    assert result.error == "invalid_output" and result.terms == rules


def test_failure_logs_code_not_content(supply_playbook, caplog):
    caplog.set_level(logging.DEBUG)
    msgs, rules = setup(supply_playbook)
    refine_terms(rules, msgs, supply_playbook, FakeModelRunner("", error=RuntimeError("secret 200 shirts")), timeout_s=2, me_id="Raju", counterparty_id="Meena")
    assert "model_runner_error" in caplog.text or "runner_error" in caplog.text
    for needle in ("200 shirts", "480 each", "Raju", "Meena", "secret"):
        assert needle not in caplog.text
