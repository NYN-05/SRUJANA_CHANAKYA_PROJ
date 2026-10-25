"""Phase 8: comparing rules and AI (FR-AIS-004, FR-EXT-004, AI_SPEC section 7)."""

from __future__ import annotations

import json

from helpers import RAJU_MEENA, make_messages, rules_terms, sample_draft, terms_by_key

from packages.contracts import Origin, ProposedTerm, TermState
from packages.intelligence.extract import extract_terms
from packages.intelligence.model.fake import FakeModelRunner
from packages.intelligence.model.refine import refine_terms


def runner_for(*terms):
    out = []
    for t in terms:
        base = {"unit": None, "state": "stated", "confidence": 0.9}
        base.update(t)
        out.append(base)
    return FakeModelRunner(json.dumps({"terms": out}))


def refine(rows, playbook, runner, rules=None):
    msgs = make_messages(rows)
    rules = rules if rules is not None else list(rules_terms(msgs, playbook).values())
    return refine_terms(rules, msgs, playbook, runner, timeout_s=5, me_id="Raju", counterparty_id="Meena"), rules


def test_agreement_gives_origin_both(supply_playbook):
    result, _ = refine(RAJU_MEENA, supply_playbook, runner_for({"key": "price", "value": "480", "unit": "each", "source_seqs": [1], "quote": "480 each"}))
    price = terms_by_key(result.terms)["price"]
    assert price.origin == Origin.BOTH and price.needs_review is False
    assert result.used_model is True and result.error is None


def test_terms_the_model_skips_stay_rules_only(supply_playbook):
    result, rules = refine(RAJU_MEENA, supply_playbook, runner_for())
    by_key = terms_by_key(result.terms)
    for r in rules:
        assert by_key[r.key].origin in (Origin.RULES, r.origin)
        assert by_key[r.key].state == r.state


def test_ai_only_grounded_term_needs_review(supply_playbook):
    rows = RAJU_MEENA + [("Raju", "late fee 500 per day")]
    msgs = make_messages(rows)
    rules = [t if t.key != "late_penalty" else t.model_copy(update={"state": TermState.MISSING, "value": None, "sources": [], "raw": None}) for t in rules_terms(msgs, supply_playbook).values()]
    runner = runner_for({"key": "late_penalty", "value": "late fee 500 per day", "source_seqs": [6], "quote": "late fee 500 per day"})
    result = refine_terms(rules, msgs, supply_playbook, runner, timeout_s=5, me_id="Raju", counterparty_id="Meena")
    lp = terms_by_key(result.terms)["late_penalty"]
    assert lp.origin == Origin.AI and lp.needs_review is True
    assert lp.state == TermState.STATED
    assert [s.seq for s in lp.sources] == [6]


def test_disagreement_marks_needs_review_and_selects_neither(supply_playbook):
    rows = RAJU_MEENA + [("Meena", "ok fine, 500 each")]
    msgs = make_messages(rows)
    price_rules = next(t for t in rules_terms(make_messages(RAJU_MEENA), supply_playbook).values() if t.key == "price")
    rules = [t if t.key != "price" else price_rules for t in rules_terms(msgs, supply_playbook).values()]
    runner = runner_for({"key": "price", "value": "500", "unit": "each", "source_seqs": [6], "quote": "500 each"})
    result = refine_terms(rules, msgs, supply_playbook, runner, timeout_s=5, me_id="Raju", counterparty_id="Meena")
    price = terms_by_key(result.terms)["price"]
    assert price.needs_review is True
    assert price.value is None
    assert {c.value.paise for c in price.candidates} == {"48000", "50000"}


def test_hinglish_advance_accepted_when_grounded(supply_playbook):
    d = sample_draft("hinglish.txt", "Kiran", "Sunil")
    kw = dict(me_id=d.me_id, counterparty_id=d.counterparty_id, eligible_ids=d.eligible_message_ids)
    rules = extract_terms(d.messages, supply_playbook, date_order="DMY", **kw)
    seq = next(m.seq for m in d.messages if "aadha advance" in m.text)
    runner = runner_for({"key": "advance", "value": "25000", "source_seqs": [seq], "quote": "aadha advance de diya"})
    result = refine_terms(rules, d.messages, supply_playbook, runner, timeout_s=5, **kw)
    adv = terms_by_key(result.terms)["advance"]
    assert adv.value.paise == "2500000" and adv.origin == Origin.BOTH


def test_every_returned_term_is_a_proposal(supply_playbook):
    result, _ = refine(RAJU_MEENA, supply_playbook, runner_for({"key": "price", "value": "480", "unit": "each", "source_seqs": [1], "quote": "480 each"}))
    assert all(isinstance(t, ProposedTerm) for t in result.terms)
    assert {t.key for t in result.terms} == {t.key for t in supply_playbook.terms}


def test_no_runner_means_rules_result(supply_playbook):
    msgs = make_messages(RAJU_MEENA)
    rules = list(rules_terms(msgs, supply_playbook).values())
    result = refine_terms(rules, msgs, supply_playbook, None, timeout_s=5, me_id="Raju", counterparty_id="Meena")
    assert result.terms == rules and result.used_model is False
