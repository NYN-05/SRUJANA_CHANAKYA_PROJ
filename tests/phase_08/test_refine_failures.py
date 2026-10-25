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


def test_answer_that_arrives_in_time_is_used(supply_playbook):
    msgs, rules = setup(supply_playbook)
    result = refine_terms(rules, msgs, supply_playbook, FakeModelRunner('{"terms": []}', delay_s=0.05), timeout_s=2, me_id="Raju", counterparty_id="Meena")
    assert result.error is None and result.used_model is True


def test_invalid_output_counts_the_problem(supply_playbook):
    msgs, rules = setup(supply_playbook)
    result = refine_terms(rules, msgs, supply_playbook, FakeModelRunner("[]"), timeout_s=2, me_id="Raju", counterparty_id="Meena")
    assert result.error == "invalid_output" and result.dropped == 1 and result.used_model is False


def test_the_runner_gets_the_prompt_it_was_built_from(supply_playbook):
    msgs, rules = setup(supply_playbook)
    runner = FakeModelRunner('{"terms": []}')
    refine_terms(rules, msgs, supply_playbook, runner, timeout_s=2, me_id="Raju", counterparty_id="Meena")
    system, data_block, schema = runner.calls[0]
    assert "untrusted" in system and "200 shirts, 480 each ok?" in data_block and schema["required"] == ["terms"]


def test_failure_logs_code_not_content(supply_playbook, caplog):
    caplog.set_level(logging.DEBUG)
    msgs, rules = setup(supply_playbook)
    refine_terms(rules, msgs, supply_playbook, FakeModelRunner("", error=RuntimeError("secret 200 shirts")), timeout_s=2, me_id="Raju", counterparty_id="Meena")
    assert "model_runner_error" in caplog.text or "runner_error" in caplog.text
    for needle in ("200 shirts", "480 each", "Raju", "Meena", "secret"):
        assert needle not in caplog.text
