"""Phase 3: the two MVP playbooks match TECHNICAL.md › Playbooks sections 2 and 3 (FR-PBK-002)."""

from __future__ import annotations

SUPPLY = {
    # key: (required, weight, type, ask_order, pairs_with)
    "parties": (True, 10, "party", 8, []),
    "scope": (True, 10, "text", 7, ["quantity"]),
    "quantity": (True, 10, "quantity", 6, ["scope"]),
    "price": (True, 15, "money", 3, []),
    "advance": (True, 10, "money", 5, ["final_payment"]),
    "delivery_date": (True, 15, "date", 1, ["final_payment"]),
    "final_payment": (True, 15, "money", 2, ["delivery_date", "advance"]),
    "late_penalty": (True, 15, "text", 4, ["delivery_date"]),
    "gst_status": (False, 0, "enum", 9, ["price"]),
}

FREELANCE = {
    "parties": (True, 10, "party", 8, []),
    "deliverable": (True, 20, "text", 1, ["deadline"]),
    "price": (True, 15, "money", 3, ["payment_schedule"]),
    "payment_schedule": (True, 15, "text", 2, ["price"]),
    "deadline": (True, 15, "date", 4, ["deliverable"]),
    "revisions": (True, 10, "quantity", 5, []),
    "ownership": (True, 5, "enum", 7, []),
    "cancellation": (True, 10, "text", 6, []),
}


def _check(pb, table):
    assert [t.key for t in pb.terms] == list(table)
    for key, (required, weight, typ, ask, pairs) in table.items():
        t = pb.term(key)
        assert (t.required, t.weight, t.type, t.ask_order, list(t.pairs_with)) == (required, weight, typ, ask, pairs), key
    assert sum(t.weight for t in pb.terms if t.required) == 100


def test_supply_order_table(supply_playbook):
    assert supply_playbook.key == "supply_order"
    _check(supply_playbook, SUPPLY)
    assert list(supply_playbook.handshake_questions) == ["delivery_date", "final_payment", "late_penalty", "price"]


def test_freelance_table(freelance_playbook):
    assert freelance_playbook.key == "freelance"
    _check(freelance_playbook, FREELANCE)
    assert list(freelance_playbook.handshake_questions) == ["deadline", "payment_schedule", "revisions", "price"]


def test_shipped_files_load_from_the_folder(playbooks_dir):
    from packages.intelligence.playbooks import load_all

    assert set(load_all(playbooks_dir)) >= {"supply_order", "freelance"}


def test_template_sets_name_the_playbook(supply_playbook, freelance_playbook):
    for pb in (supply_playbook, freelance_playbook):
        assert pb.recap_template_set == pb.key and pb.suggestions_template_set == pb.key


def test_every_term_with_a_parser_uses_registered_ones(supply_playbook, freelance_playbook):
    from packages.intelligence.rules import PARSERS

    for pb in (supply_playbook, freelance_playbook):
        for t in pb.terms:
            assert set(t.parsers) <= PARSERS


def test_property_hint_keywords_and_gst_condition(supply_playbook, freelance_playbook):
    hints = {h.id: h for h in supply_playbook.legal_hints}
    assert {"flat", "lease", "zameen"} <= set(hints["property_hint"].keywords)
    assert hints["gst_note"].term_missing == "gst_status" and hints["value_hint"].keywords == []
    assert freelance_playbook.legal_hints[0].term_missing == "ownership"


def test_supply_ambiguity_rules(supply_playbook):
    ids = {r.id: r.type for r in supply_playbook.ambiguity_rules}
    assert ids == {
        "rel_date": "AMBIGUOUS_DATE",
        "partial_date": "AMBIGUOUS_DATE",
        "order_date": "AMBIGUOUS_DATE",
        "approx_amount": "AMBIGUOUS_AMOUNT",
        "vague_qty": "VAGUE_QUANTITY",
        "vague_pay": "VAGUE_PAYMENT",
        "half_adv": "VAGUE_PAYMENT",
    }
    rel = next(r for r in supply_playbook.ambiguity_rules if r.id == "rel_date")
    assert "5 to 12 days" in rel.reason["en"]
    assert rel.reason["hi"]


def test_supply_legal_hints(supply_playbook):
    assert {h.id for h in supply_playbook.legal_hints} == {"property_hint", "value_hint", "gst_note"}
    for h in supply_playbook.legal_hints:
        assert "lawyer" in h.text["en"].lower() or "ca" in h.text["en"].lower().split()


def test_model_aliases_cover_q62_keys(supply_playbook, freelance_playbook):
    # I-02: model vocabulary maps onto playbook keys
    for alias, key in [
        ("buyer", "parties"),
        ("seller", "parties"),
        ("item", "scope"),
        ("unit_price", "price"),
        ("total_amount", "price"),
        ("advance_amount", "advance"),
        ("balance_payment_date", "final_payment"),
    ]:
        assert supply_playbook.key_for_alias(alias) == key, alias
    for alias, key in [("client", "parties"), ("freelancer", "parties"), ("scope", "deliverable"), ("fee", "price"), ("payment_date", "payment_schedule"), ("ownership_transfer", "ownership")]:
        assert freelance_playbook.key_for_alias(alias) == key, alias


def test_every_user_string_has_english_and_hindi(supply_playbook, freelance_playbook):
    for pb in (supply_playbook, freelance_playbook):
        assert pb.title["en"] and pb.title["hi"]
        for t in pb.terms:
            assert t.label["en"] and t.label["hi"], t.key
            assert t.cues["en"] or t.type == "party", f"{pb.key}.{t.key} needs English cues"
        for r in pb.ambiguity_rules:
            assert r.reason["en"] and r.reason["hi"], r.id
