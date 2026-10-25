"""Phase 4: suggestion text in three tones from fixed templates (FR-SUG-002, FR-SUG-003)."""

from __future__ import annotations

import pytest

from packages.contracts import DateValue, MoneyValue, PartyValue, QuantityValue, TextValue, Tone
from packages.intelligence.suggest import build_suggestion

KNOWN = {
    "parties": PartyValue(names=["Raju", "Meena"]),
    "scope": TextValue(text="shirts"),
    "quantity": QuantityValue(amount=200, unit="shirts"),
    "price": MoneyValue(paise="48000", per="item"),
    "advance": MoneyValue(paise="4800000"),
}
TARGETS = ["delivery_date", "final_payment"]
THREATS = ("legal action", "court", "police", "notice", "or else", "lawyer")


def test_polite_english_exact_text_with_date(supply_playbook):
    values = dict(KNOWN, delivery_date=DateValue(date="2026-11-15"))
    s = build_suggestion(TARGETS, Tone.POLITE, values, supply_playbook, "en")
    assert s.text == "Just to confirm, delivery by 15 Nov 2026 and the balance ₹48,000 on delivery, right?"
    assert s.target_term_keys == TARGETS and s.tone == Tone.POLITE and s.language == "en"
    assert s.needs_user_input == []


def test_unknown_date_becomes_a_visible_placeholder(supply_playbook):
    s = build_suggestion(TARGETS, Tone.POLITE, KNOWN, supply_playbook, "en")
    assert "[delivery date]" in s.text
    assert s.needs_user_input == ["delivery_date"]
    assert "{" not in s.text and "None" not in s.text


def test_balance_is_total_minus_advance(supply_playbook):
    s = build_suggestion(TARGETS, Tone.CASUAL, KNOWN, supply_playbook, "en")
    assert "₹48,000" in s.text  # 200 x ₹480 - ₹48,000


def test_three_tones_differ_but_share_facts(supply_playbook):
    values = dict(KNOWN, delivery_date=DateValue(date="2026-11-15"))
    texts = {t: build_suggestion(TARGETS, t, values, supply_playbook, "en").text for t in Tone}
    assert len(set(texts.values())) == 3
    for text in texts.values():
        assert "15 Nov 2026" in text and "₹48,000" in text


def test_firm_tone_never_threatens(supply_playbook):
    for lang in ("en", "hi"):
        text = build_suggestion(TARGETS, Tone.FIRM, KNOWN, supply_playbook, lang).text.lower()
        for word in THREATS:
            assert word not in text


def test_hindi_suggestion(supply_playbook):
    values = dict(KNOWN, delivery_date=DateValue(date="2026-11-15"))
    s = build_suggestion(TARGETS, Tone.POLITE, values, supply_playbook, "hi")
    assert "15 नवंबर 2026" in s.text and "₹48,000" in s.text
    assert any("ऀ" <= ch <= "ॿ" for ch in s.text)


@pytest.mark.parametrize("target", [["late_penalty"], ["price"], ["advance"], ["quantity"], ["scope"]])
def test_other_gaps_have_text(supply_playbook, target):
    for tone in Tone:
        s = build_suggestion(target, tone, KNOWN, supply_playbook, "en")
        assert s.text and "{" not in s.text


def test_missing_pair_template_falls_back_to_the_top_target(supply_playbook):
    s = build_suggestion(["price", "scope"], Tone.POLITE, KNOWN, supply_playbook, "en")
    assert s.target_term_keys == ["price"] and s.text == "Just to confirm, the price is ₹480 each, right?"


def test_missing_template_raises_a_typed_error(supply_playbook):
    from packages.intelligence.suggest import TemplateMissing

    with pytest.raises(TemplateMissing) as err:
        build_suggestion(["no_such_term"], Tone.POLITE, KNOWN, supply_playbook, "en")
    assert (err.value.key, err.value.tone, err.value.lang) == ("no_such_term", "polite", "en")


def test_unknown_balance_is_a_placeholder_for_the_final_payment_term(supply_playbook):
    s = build_suggestion(["final_payment"], Tone.CASUAL, {}, supply_playbook, "en")
    assert "[balance]" in s.text and s.needs_user_input == ["final_payment"]
    hi = build_suggestion(["final_payment"], Tone.CASUAL, {}, supply_playbook, "hi")
    assert "[बाकी रकम]" in hi.text


def test_hindi_has_no_latin_words_when_all_values_are_known(supply_playbook):
    import re

    values = dict(KNOWN, delivery_date=DateValue(date="2026-11-15"))
    for tone in Tone:
        text = build_suggestion(TARGETS, tone, values, supply_playbook, "hi").text
        assert not re.search(r"[A-Za-z]", text), text


def test_same_facts_in_all_tones_for_every_supply_pair(supply_playbook):
    values = dict(KNOWN, delivery_date=DateValue(date="2026-11-15"), late_penalty=TextValue(text="₹500 per day"))
    for targets in (["delivery_date", "late_penalty"], ["advance", "final_payment"], ["quantity", "scope"]):
        texts = [build_suggestion(targets, t, values, supply_playbook, "en").text for t in Tone]
        assert len(set(texts)) == 3 and all("[" not in x for x in texts)


def test_suggestion_has_no_send_capability(supply_playbook):
    s = build_suggestion(TARGETS, Tone.POLITE, KNOWN, supply_playbook, "en")
    assert not any(hasattr(s, name) for name in ("send", "post", "deliver"))


def test_freelance_deadline_and_deliverable(freelance_playbook):
    values = {"deliverable": TextValue(text="a logo in 3 colours"), "deadline": DateValue(date="2026-11-30")}
    s = build_suggestion(["deadline", "deliverable"], Tone.POLITE, values, freelance_playbook, "en")
    assert s.text == "To confirm, you will receive a logo in 3 colours by 30 Nov 2026. Does that work for you?"
