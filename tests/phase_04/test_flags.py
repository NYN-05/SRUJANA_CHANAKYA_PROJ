"""Phase 4: flags with plain reasons and sources (FR-FLG-001 to 003, 005, 006; FR-PBK-003)."""

from __future__ import annotations

from helpers import RAJU_MEENA, make_messages, rules_terms, sample_draft

from packages.contracts import FlagType
from packages.intelligence.extract import extract_terms
from packages.intelligence.flags import build_flags


def flags_for(rows, playbook, me="Raju", cp="Meena"):
    msgs = make_messages(rows)
    terms = list(rules_terms(msgs, playbook, me=me, counterparty=cp).values())
    return build_flags(terms, playbook, msgs, me_id=me, counterparty_id=cp), msgs


def by_type(flags, ftype):
    return [f for f in flags if f.type == ftype]


def test_raju_meena_flags(supply_playbook):
    flags, msgs = flags_for(RAJU_MEENA, supply_playbook)
    amb = by_type(flags, FlagType.AMBIGUOUS_DATE)
    assert [f.term_key for f in amb] == ["delivery_date"]
    assert amb[0].rule_id == "rel_date"
    assert "5 to 12 days" in amb[0].reason_en
    assert [s.message_id for s in amb[0].source_refs] == [msgs[1].id]
    missing = sorted(f.term_key for f in by_type(flags, FlagType.MISSING_TERM))
    assert missing == ["final_payment", "late_penalty"]
    assert not by_type(flags, FlagType.CONTRADICTION)


def test_non_required_term_never_missing(supply_playbook):
    flags, _ = flags_for(RAJU_MEENA, supply_playbook)
    assert "gst_status" not in {f.term_key for f in by_type(flags, FlagType.MISSING_TERM)}


def test_gst_note_hint_when_gst_not_mentioned(supply_playbook):
    flags, _ = flags_for(RAJU_MEENA, supply_playbook)
    hints = by_type(flags, FlagType.REGISTRATION_HINT)
    assert any(f.rule_id == "gst_note" for f in hints)


def test_approx_amount_flag(supply_playbook):
    flags, _ = flags_for([("Raju", "approx 50k for all"), ("Meena", "ok")], supply_playbook)
    f = by_type(flags, FlagType.AMBIGUOUS_AMOUNT)
    assert f and f[0].term_key == "price" and f[0].source_refs


def test_vague_quantity_and_payment_flags(supply_playbook):
    flags, _ = flags_for([("Raju", "send a few shirts"), ("Meena", "ok, will pay soon")], supply_playbook)
    assert by_type(flags, FlagType.VAGUE_QUANTITY)
    assert by_type(flags, FlagType.VAGUE_PAYMENT)


def test_contradiction_lists_both_sources_and_values(supply_playbook):
    d = sample_draft("contradictory.txt", "Patel", "Sai")
    terms = extract_terms(d.messages, supply_playbook, me_id=d.me_id, counterparty_id=d.counterparty_id, date_order="DMY", eligible_ids=d.eligible_message_ids)
    flags = build_flags(terms, supply_playbook, d.messages, me_id=d.me_id, counterparty_id=d.counterparty_id)
    c = by_type(flags, FlagType.CONTRADICTION)
    assert len(c) == 1 and c[0].term_key == "price"
    assert len(c[0].source_refs) == 2
    assert "₹50,000" in c[0].reason_en and "₹45,000" in c[0].reason_en
    assert "#2" in c[0].reason_en and "#4" in c[0].reason_en


def test_unacknowledged(supply_playbook):
    flags, _ = flags_for([("Raju", "200 shirts, 480 each"), ("Meena", "ok"), ("Raju", "late fee 500 per day")], supply_playbook)
    un = by_type(flags, FlagType.UNACKNOWLEDGED)
    assert [f.term_key for f in un] == ["late_penalty"]
    assert "Raju" in un[0].reason_en


def test_property_keywords_raise_registration_hint(supply_playbook):
    flags, _ = flags_for([("Raju", "flat on lease, rent 20,000"), ("Meena", "ok")], supply_playbook)
    hint = [f for f in by_type(flags, FlagType.REGISTRATION_HINT) if f.rule_id == "property_hint"]
    assert hint and "lawyer" in hint[0].reason_en.lower()


def test_every_flag_is_well_formed(supply_playbook):
    flags, _ = flags_for(RAJU_MEENA + [("Raju", "approx 50k"), ("Raju", "late fee 500 per day")], supply_playbook)
    assert flags
    for f in flags:
        assert f.reason_en.strip() and f.reason_hi.strip(), f
        assert len(f.reason_en) < 300
        if f.type not in (FlagType.MISSING_TERM, FlagType.REGISTRATION_HINT):
            assert f.source_refs, f"{f.type} must cite a source"


def test_reasons_use_no_legal_jargon(supply_playbook):
    flags, _ = flags_for(RAJU_MEENA, supply_playbook)
    for f in flags:
        low = f.reason_en.lower()
        for word in ("hereinafter", "whereas", "consideration", "breach", "liable", "enforceable"):
            assert word not in low


def test_needs_review_terms_become_flags(supply_playbook):
    msgs = make_messages(RAJU_MEENA)
    terms = list(rules_terms(msgs, supply_playbook).values())
    price = next(t for t in terms if t.key == "price")
    reviewed = [t if t.key != "price" else price.model_copy(update={"needs_review": True}) for t in terms]
    flags = build_flags(reviewed, supply_playbook, msgs, me_id="Raju", counterparty_id="Meena")
    assert [f.term_key for f in by_type(flags, FlagType.NEEDS_REVIEW)] == ["price"]
