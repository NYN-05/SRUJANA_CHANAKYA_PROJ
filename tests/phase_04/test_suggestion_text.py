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


def test_suggestion_has_no_send_capability(supply_playbook):
    s = build_suggestion(TARGETS, Tone.POLITE, KNOWN, supply_playbook, "en")
    assert not any(hasattr(s, name) for name in ("send", "post", "deliver"))


def test_freelance_deadline_and_deliverable(freelance_playbook):
    values = {"deliverable": TextValue(text="a logo in 3 colours"), "deadline": DateValue(date="2026-11-30")}
    s = build_suggestion(["deadline", "deliverable"], Tone.POLITE, values, freelance_playbook, "en")
    assert s.text == "To confirm, you will receive a logo in 3 colours by 30 Nov 2026. Does that work for you?"
