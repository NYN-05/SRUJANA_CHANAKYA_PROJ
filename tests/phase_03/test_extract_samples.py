"""Phase 3: rules-only extraction on the sample chats (FR-EXT-001, FR-EXT-002, FR-IMP-007)."""

from __future__ import annotations

from helpers import sample_draft, terms_by_key

from packages.contracts import Origin, TermState
from packages.intelligence.extract import extract_terms

S, U, C, M = TermState.STATED, TermState.UNCLEAR, TermState.CONTRADICTED, TermState.MISSING


def run(name, me, cp, playbook):
    d = sample_draft(name, me, cp, playbook.key)
    terms = extract_terms(
        d.messages,
        playbook,
        me_id=d.me_id,
        counterparty_id=d.counterparty_id,
        date_order="DMY",
        eligible_ids=d.eligible_message_ids,
    )
    seq_of = {m.id: m.seq for m in d.messages}
    return d, terms_by_key(terms), seq_of


def seqs(term, seq_of):
    return sorted(seq_of[s.message_id] for s in term.sources)


def test_every_playbook_term_is_returned(supply_playbook):
    _, t, _ = run("ambiguous.txt", "Raju", "Meena", supply_playbook)
    assert set(t) == {x.key for x in supply_playbook.terms}


def test_ambiguous_sample_states(supply_playbook):
    d, t, seq_of = run("ambiguous.txt", "Raju", "Meena", supply_playbook)
    states = {k: v.state for k, v in t.items()}
    assert states == {
        "parties": S,
        "scope": S,
        "quantity": S,
        "price": S,
        "advance": S,
        "delivery_date": U,
        "final_payment": M,
        "late_penalty": M,
        "gst_status": M,
    }
    assert t["parties"].value.names == [d.me_id, d.counterparty_id]
    assert t["scope"].value.text == "shirts"
    assert (t["quantity"].value.amount, t["quantity"].value.unit) == (200, "shirts")
    assert t["price"].value.paise == "48000" and t["price"].value.per == "item"
    assert t["advance"].value.paise == "4800000"
    assert t["delivery_date"].value is None
    assert t["delivery_date"].unclear_reason == "rel_date"


def test_ambiguous_sample_sources(supply_playbook):
    _, t, seq_of = run("ambiguous.txt", "Raju", "Meena", supply_playbook)
    assert seqs(t["quantity"], seq_of) == [1]
    assert seqs(t["price"], seq_of) == [1]
    assert seqs(t["delivery_date"], seq_of) == [2]
    assert seqs(t["advance"], seq_of) == [3, 4]  # "advance half now" and "done sent 48000"
    assert t["final_payment"].sources == [] and t["late_penalty"].sources == []
    for key in ("quantity", "price", "delivery_date"):
        for src in t[key].sources:
            assert src.quote and src.end > src.start


def test_rules_origin_and_no_review(supply_playbook):
    _, t, _ = run("ambiguous.txt", "Raju", "Meena", supply_playbook)
    for term in t.values():
        if term.state != M:
            assert term.origin == Origin.RULES
            assert term.needs_review is False


def test_clean_sample_all_required_terms_stated(supply_playbook):
    _, t, seq_of = run("clean.txt", "Anita", "Rohit", supply_playbook)
    for key in supply_playbook.required_keys:
        assert t[key].state == S, key
    assert t["quantity"].value.amount == 500
    assert t["price"].value.paise == "12000" and t["price"].value.per == "item"
    assert t["delivery_date"].value.date == "2026-11-05"
    assert t["advance"].value.paise == "2000000"
    assert t["final_payment"].value.when == "on_delivery"
    assert t["final_payment"].value.paise == "4000000"
    assert "500 per day" in t["late_penalty"].raw
    assert seqs(t["delivery_date"], seq_of) == [2, 3]


def test_clean_total_is_consistency_not_conflict(supply_playbook):
    _, t, _ = run("clean.txt", "Anita", "Rohit", supply_playbook)
    assert t["price"].state == S
    assert t["price"].candidates == [] or len({c.value.paise for c in t["price"].candidates}) == 1


def test_contradictory_sample_price_conflict(supply_playbook):
    _, t, seq_of = run("contradictory.txt", "Patel", "Sai", supply_playbook)
    price = t["price"]
    assert price.state == C
    assert price.value is None, "neither value is selected for a conflict"
    assert {c.value.paise for c in price.candidates} == {"5000000", "4500000"}
    by_value = {c.value.paise: sorted(seq_of[s.message_id] for s in c.sources) for c in price.candidates}
    assert by_value == {"5000000": [2], "4500000": [4]}
    assert t["delivery_date"].value.date == "2026-11-20"
    assert t["quantity"].value.amount == 100


def test_contradictory_system_line_is_never_a_source(supply_playbook):
    _, t, seq_of = run("contradictory.txt", "Patel", "Sai", supply_playbook)
    for term in t.values():
        assert 1 not in seqs(term, seq_of)


def test_hinglish_sample(supply_playbook):
    _, t, _ = run("hinglish.txt", "Kiran", "Sunil", supply_playbook)
    assert t["price"].value.paise == "5000000" and t["price"].value.per == "total"
    assert t["quantity"].value.amount == 300
    assert t["advance"].value.paise == "2500000"  # aadha of the total
    assert t["final_payment"].state == S
    assert t["final_payment"].value.days == 30
