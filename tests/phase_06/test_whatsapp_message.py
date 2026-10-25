"""Phase 6: the message the counterparty sees (FR-RCP-003, FR-RCP-004, S12)."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue
from packages.ingest.recap import build_recap, build_whatsapp_message

LEGAL_WORDS = ("contract", "agreement", "legal", "lawyer", "court", "binding", "hereby", "terms and conditions", "not legal advice")


@pytest.fixture
def recap(vault, supply_playbook):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    v = vault.create_version(deal)
    draft = build_recap(vault.agreed_terms(deal), supply_playbook, "en", "Meena", deal_id=deal, version_n=v.n)
    return vault.create_recap(deal, v.n, draft)


def test_exact_message(recap):
    msg = build_whatsapp_message(recap)
    assert msg == (
        "Hi Meena, just confirming what we discussed:\n"
        "• 200 shirts at ₹480 each = ₹96,000\n"
        "• ₹48,000 advance received\n"
        "• Delivery by 15 Nov 2026\n"
        f"If all correct, reply: CONFIRM {recap.echo_code}"
    )
    assert msg == recap.text


def test_no_legal_words_in_the_message(recap):
    low = build_whatsapp_message(recap).lower()
    for word in LEGAL_WORDS:
        assert word not in low


def test_hindi_closing_keeps_confirm_in_latin(vault, supply_playbook):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    v = vault.create_version(deal)
    draft = build_recap(vault.agreed_terms(deal), supply_playbook, "hi", "Meena", deal_id=deal, version_n=v.n)
    r = vault.create_recap(deal, v.n, draft)
    assert build_whatsapp_message(r).endswith(f"अगर सब सही है तो जवाब दें: CONFIRM {r.echo_code}")
