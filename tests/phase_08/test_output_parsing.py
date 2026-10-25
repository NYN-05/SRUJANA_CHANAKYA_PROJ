"""Phase 8: model output is never trusted (AI_SPEC section 4; I-02, I-03, I-04; Q-64)."""

from __future__ import annotations

import json

import pytest
from helpers import RAJU_MEENA, make_messages

from packages.contracts import DateValue, EventValue, MoneyValue, PartialDateValue, QuantityValue, TermState
from packages.intelligence.model.output import parse_model_output

MSGS = make_messages(RAJU_MEENA)


def raw(*terms):
    return json.dumps({"terms": list(terms)})


def term(**kw):
    base = {"key": "price", "value": "480", "unit": "each", "state": "stated", "source_seqs": [1], "quote": "480 each", "confidence": 0.9}
    base.update(kw)
    return base


def parse(text, playbook):
    return parse_model_output(text, playbook, MSGS)


def test_valid_money_term(supply_playbook):
    terms, problems = parse(raw(term()), supply_playbook)
    assert problems == []
    assert terms[0].key == "price"
    assert terms[0].value == MoneyValue(paise="48000", per="item")
    assert terms[0].state == TermState.STATED
    assert terms[0].source_seqs == [1]


@pytest.mark.parametrize("bad", ["not json", "", "[]", '{"terms": "x"}', '{"other": []}', "{" * 1000])
def test_invalid_output_is_a_problem_not_an_exception(supply_playbook, bad):
    terms, problems = parse(bad, supply_playbook)
    assert terms == [] and problems and problems[0].kind == "invalid_json"


def test_unknown_key_dropped(supply_playbook):
    terms, problems = parse(raw(term(key="discount")), supply_playbook)
    assert terms == [] and [p.kind for p in problems] == ["unknown_key"]


@pytest.mark.parametrize("alias,key", [("unit_price", "price"), ("advance_amount", "advance"), ("balance_payment_date", "final_payment")])
def test_model_aliases_map_to_playbook_keys(supply_playbook, alias, key):
    terms, _ = parse(raw(term(key=alias)), supply_playbook)
    assert terms and terms[0].key == key


@pytest.mark.parametrize("state", ["confirmed", "clear", "", None, 5])
def test_status_outside_contract_becomes_needs_review(supply_playbook, state):
    terms, problems = parse(raw(term(state=state)), supply_playbook)
    assert terms and terms[0].needs_review is True
    assert any(p.kind == "bad_state" for p in problems)


@pytest.mark.parametrize("value", [None, 12.5, "lots", "", [1, 2]])
def test_malformed_money_value_becomes_needs_review(supply_playbook, value):
    terms, _ = parse(raw(term(value=value)), supply_playbook)
    assert terms and terms[0].needs_review is True and terms[0].value is None


def test_month_day_date_gets_partial_prefix(supply_playbook):
    terms, _ = parse(raw(term(key="delivery_date", value="11-15", unit=None, quote="next week", source_seqs=[2])), supply_playbook)
    assert terms[0].value == PartialDateValue(date="--11-15")


def test_full_date(supply_playbook):
    terms, _ = parse(raw(term(key="delivery_date", value="2026-11-15", unit=None, quote="x", source_seqs=[2])), supply_playbook)
    assert terms[0].value == DateValue(date="2026-11-15")


def test_event_value(supply_playbook):
    terms, _ = parse(raw(term(key="final_payment", value="on_delivery", unit=None, quote="x", source_seqs=[2])), supply_playbook)
    assert terms[0].value == EventValue(event="on_delivery") or getattr(terms[0].value, "when", None) == "on_delivery"


def test_quantity_is_integer_with_null_unit_for_revisions(freelance_playbook):
    terms, _ = parse_model_output(raw(term(key="revisions", value=2, unit=None, quote="2 revisions")), freelance_playbook, MSGS)
    assert terms[0].value == QuantityValue(amount=2, unit=None)


def test_source_positions_must_be_integers(supply_playbook):
    terms, problems = parse(raw(term(source_seqs=["m1"])), supply_playbook)
    assert terms == [] or terms[0].needs_review
    assert any(p.kind == "bad_source" for p in problems)


def test_extra_fields_are_ignored_and_cannot_confirm(supply_playbook):
    terms, _ = parse(raw(term(confirmed=True, origin="user", needs_review=False)), supply_playbook)
    assert not hasattr(terms[0], "confirmed")


def test_confidence_clamped_or_flagged(supply_playbook):
    terms, _ = parse(raw(term(confidence=7)), supply_playbook)
    assert 0.0 <= terms[0].confidence <= 1.0
