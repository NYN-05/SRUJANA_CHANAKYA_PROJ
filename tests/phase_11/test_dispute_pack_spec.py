"""Phase 11c (deferred, R-02): basic dispute pack. FR-DSP-001 to 005, LIMITS L1, L9, L13."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

pytestmark = pytest.mark.deferred
DISCLAIMER = "Drafting aid, not legal advice. The certificate is an unsigned draft and must be completed by the person responsible for the device."
PARTS = {"timeline", "evidence_index", "versions", "certificate", "how_to_verify", "receipt_bundle"}


@pytest.fixture
def deal(vault):
    d, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, d)
    vault.create_version(d)
    return d


def test_preview_lists_parts_size_and_pages(vault, deal):
    p = vault.dispute_pack_preview(deal, parts=PARTS)
    assert p.pages > 0 and p.size_bytes > 0 and set(p.parts) == PARTS


def test_disclaimer_is_first_and_draft_on_every_page(vault, deal, tmp_path):
    pdf_text_pages = vault.export_dispute_pack(deal, tmp_path, parts=PARTS).page_texts
    assert pdf_text_pages[0].startswith(DISCLAIMER)
    assert all("DRAFT" in page for page in pdf_text_pages if "Section 63" in page)


def test_each_part_can_be_switched_off(vault, deal, tmp_path):
    pack = vault.export_dispute_pack(deal, tmp_path, parts=PARTS - {"certificate"})
    assert not any("Section 63" in p for p in pack.page_texts)


def test_never_called_a_legal_instrument(vault, deal, tmp_path):
    text = " ".join(vault.export_dispute_pack(deal, tmp_path, parts=PARTS).page_texts).lower()
    assert "court-ready evidence package" in text
    for banned in ("legally binding", "admissible", "guaranteed", "proof of authenticity"):
        assert banned not in text


def test_hindi_text_is_shaped(vault, deal, tmp_path):
    pack = vault.export_dispute_pack(deal, tmp_path, parts=PARTS, language="hi")
    assert pack.missing_glyphs == 0
