"""Phase 6: recap drafts from confirmed terms with fixed templates (FR-RCP-001, FR-RCP-002, I-07, ADR-010)."""

from __future__ import annotations

import pytest

from packages.contracts import (
    AgreedTerm,
    DateValue,
    MoneyValue,
    Origin,
    PartyValue,
    PaymentValue,
    QuantityValue,
    SourceRef,
    TextValue,
)
from packages.ingest.recap import build_recap

TS = "2026-10-24T11:42:00+05:30"


def agreed(key, value, seq):
    return AgreedTerm(
        key=key,
        value=value,
        sources=[SourceRef(kind="message", message_id=f"m{seq}", seq=seq, start=0, end=1, quote="x")],
        confirmed_by="me",
        confirmed_at=TS,
        origin=Origin.RULES,
        acknowledged_by_other=True,
    )


RAJU_MEENA = {
    "parties": agreed("parties", PartyValue(names=["Raju", "Meena"]), 1),
    "scope": agreed("scope", TextValue(text="shirts"), 1),
    "quantity": agreed("quantity", QuantityValue(amount=200, unit="shirts"), 1),
    "price": agreed("price", MoneyValue(paise="48000", per="item"), 1),
    "advance": agreed("advance", PaymentValue(paise="4800000", when="paid"), 4),
    "delivery_date": agreed("delivery_date", DateValue(date="2026-11-15"), 12),
}


def test_english_lines_exact(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert [l.text for l in r.lines] == [
        "200 shirts at ₹480 each = ₹96,000",
        "₹48,000 advance received",
        "Delivery by 15 Nov 2026",
    ]
    assert r.body_text == (
        "Hi Meena, just confirming what we discussed:\n"
        "• 200 shirts at ₹480 each = ₹96,000\n"
        "• ₹48,000 advance received\n"
        "• Delivery by 15 Nov 2026"
    )
    assert (r.deal_id, r.version_n, r.language) == ("d1", 1, "en")


def test_lines_cite_sources(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    by_key = {l.term_key: l for l in r.lines}
    assert by_key["price"].sources == ["m1"]
    assert by_key["advance"].sources == ["m4"]
    assert by_key["delivery_date"].sources == ["m12"]


def test_omitted_terms_are_listed(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert dict(r.omitted_terms) == {"final_payment": "not_confirmed", "late_penalty": "not_confirmed"}


def test_balance_and_penalty_lines(supply_playbook):
    terms = dict(
        RAJU_MEENA,
        final_payment=agreed("final_payment", PaymentValue(paise="4800000", when="on_delivery"), 13),
        late_penalty=agreed("late_penalty", TextValue(text="₹500 per day is deducted"), 14),
    )
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=2)
    texts = [l.text for l in r.lines]
    assert "Balance ₹48,000 on delivery" in texts
    assert "If delivery is late: ₹500 per day is deducted" in texts
    assert r.omitted_terms == []


@pytest.mark.parametrize(
    "value,text",
    [
        (PaymentValue(paise="4800000", when="after_delivery", days=30), "Balance ₹48,000 within 30 days of delivery"),
        (PaymentValue(paise="4800000", when="on_date", date="2026-12-01"), "Balance ₹48,000 on 1 Dec 2026"),
    ],
)
def test_balance_when_variants(supply_playbook, value, text):
    r = build_recap(dict(RAJU_MEENA, final_payment=agreed("final_payment", value, 13)), supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert text in [l.text for l in r.lines]


def test_advance_due_variant(supply_playbook):
    terms = dict(RAJU_MEENA, advance=agreed("advance", PaymentValue(paise="4800000", when="on_date", date="2026-10-20"), 4))
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert "₹48,000 advance due on 20 Oct 2026" in [l.text for l in r.lines]


def test_incomplete_combined_line_is_omitted_not_guessed(supply_playbook):
    terms = {k: v for k, v in RAJU_MEENA.items() if k != "quantity"}
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    omitted = dict(r.omitted_terms)
    assert omitted["quantity"] == "not_confirmed"
    assert omitted["price"] == "incomplete_line" and omitted["scope"] == "incomplete_line"
    assert not any("₹480" in l.text for l in r.lines)


def test_hindi_recap(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "hi", "Meena", deal_id="d1", version_n=1)
    assert r.body_text.startswith("नमस्ते Meena, हमारी बात का सार यह है:")
    assert "डिलीवरी 15 नवंबर 2026 तक" in [l.text for l in r.lines]
    assert "₹48,000 एडवांस मिल गया" in [l.text for l in r.lines]
    for line in r.lines:
        assert "{" not in line.text and "}" not in line.text
        assert any("ऀ" <= ch <= "ॿ" for ch in line.text)


def test_hindi_rupee_not_doubled(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "hi", "Meena", deal_id="d1", version_n=1)
    assert "₹₹" not in r.body_text


def test_freelance_recap(freelance_playbook):
    terms = {
        "parties": agreed("parties", PartyValue(names=["Kiran", "Nova"]), 1),
        "deliverable": agreed("deliverable", TextValue(text="Logo in 3 colours, PNG and SVG"), 1),
        "price": agreed("price", MoneyValue(paise="800000", per="total"), 1),
        "payment_schedule": agreed("payment_schedule", TextValue(text="50% advance, rest on completion"), 2),
        "deadline": agreed("deadline", DateValue(date="2026-11-30"), 2),
        "revisions": agreed("revisions", QuantityValue(amount=2, unit=None), 1),
    }
    r = build_recap(terms, freelance_playbook, "en", "Nova", deal_id="d2", version_n=1)
    assert [l.text for l in r.lines] == [
        "Work: Logo in 3 colours, PNG and SVG",
        "Fee: ₹8,000",
        "Payments: 50% advance, rest on completion",
        "Deadline: 30 Nov 2026",
        "Changes included: 2",
    ]
    assert dict(r.omitted_terms) == {"ownership": "not_confirmed", "cancellation": "not_confirmed"}


def test_total_price_has_its_own_line(supply_playbook):
    terms = dict(RAJU_MEENA, price=agreed("price", MoneyValue(paise="9600000", per="total"), 1))
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert "200 shirts for ₹96,000" in [l.text for l in r.lines]


def test_balance_without_an_amount_still_reads_well(supply_playbook):
    terms = dict(RAJU_MEENA, final_payment=agreed("final_payment", PaymentValue(when="on_delivery"), 13))
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert "Balance due on delivery" in [l.text for l in r.lines]


def test_unusable_value_is_left_out_not_guessed(supply_playbook):
    terms = dict(RAJU_MEENA, final_payment=agreed("final_payment", PaymentValue(), 13))
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert not any(l.term_key == "final_payment" for l in r.lines)
    assert dict(r.omitted_terms)["final_payment"] == "incomplete_line"


def test_unconfirmed_required_terms_without_a_line_are_listed(supply_playbook):
    terms = {k: v for k, v in RAJU_MEENA.items() if k != "parties"}
    r = build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert dict(r.omitted_terms)["parties"] == "not_confirmed"


def test_optional_terms_are_never_listed_as_omitted(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert "gst_status" not in dict(r.omitted_terms)


def test_draft_carries_the_closing_line_but_no_code(supply_playbook):
    r = build_recap(RAJU_MEENA, supply_playbook, "hi", "Meena", deal_id="d1", version_n=1)
    assert r.closing == "अगर सब सही है तो जवाब दें: CONFIRM {code}"
    assert "CONFIRM" not in r.body_text


def test_a_date_shown_for_the_balance_is_the_balances_own(supply_playbook):
    terms = dict(
        RAJU_MEENA,
        advance=agreed("advance", PaymentValue(paise="4800000", when="on_date", date="2026-10-20"), 4),
        final_payment=agreed("final_payment", PaymentValue(paise="4800000", when="on_date", date="2026-12-01"), 13),
    )
    texts = [l.text for l in build_recap(terms, supply_playbook, "en", "Meena", deal_id="d1", version_n=1).lines]
    assert "₹48,000 advance due on 20 Oct 2026" in texts and "Balance ₹48,000 on 1 Dec 2026" in texts


def test_builder_is_deterministic(supply_playbook):
    a = build_recap(RAJU_MEENA, supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    b = build_recap(dict(reversed(list(RAJU_MEENA.items()))), supply_playbook, "en", "Meena", deal_id="d1", version_n=1)
    assert a == b


def test_unsupported_language(supply_playbook):
    with pytest.raises(ValueError):
        build_recap(RAJU_MEENA, supply_playbook, "kn", "Meena", deal_id="d1", version_n=1)  # Kannada is P1 (11d)
