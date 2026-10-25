"""Phase 5: vault logs carry events and counts only (Architecture section 13, NFR-PRV-002)."""

from __future__ import annotations

import logging

from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue

FORBIDDEN = ["200 shirts", "next week", "Raju", "Meena", "48000", "ambiguous.txt", "correct horse battery staple"]


def test_no_content_in_logs(vault, caplog):
    caplog.set_level(logging.DEBUG)
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-15"))
    vault.create_version(deal)
    vault.self_check()
    text = caplog.text
    assert caplog.records, "the vault should log events (names and counts)"
    for needle in FORBIDDEN:
        assert needle not in text, f"log contains content: {needle}"
