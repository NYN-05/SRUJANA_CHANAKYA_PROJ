"""Phase 11d (deferred): P1 items from PRD section 8.18. Each ships behind its own feature flag."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.deferred


def test_privacy_mask_prd_example():
    from packages.vault.mask import mask_text

    out = mask_text("send to a/c 123456789012, IFSC SBIN0001234, ₹48,000 on 15 Nov 2026")
    assert out == "send to a/c [ACCOUNT_1], IFSC [BANK_CODE_1], ₹48,000 on 15 Nov 2026"


def test_mask_tokens_are_stable_within_an_export():
    from packages.vault.mask import mask_text

    out = mask_text("a/c 123456789012 again a/c 123456789012 and a/c 987654321098")
    assert out.count("[ACCOUNT_1]") == 2 and "[ACCOUNT_2]" in out


@pytest.mark.parametrize("text,token", [("my PAN ABCDE1234F", "[PAN_1]"), ("upi raju@okaxis", "[UPI_1]"), ("OTP is 482913", "[SECRET_1]")])
def test_mask_patterns(text, token):
    from packages.vault.mask import mask_text

    assert token in mask_text(text)


def test_aadhaar_needs_valid_verhoeff_checksum():
    from packages.vault.mask import mask_text

    assert "[AADHAAR_1]" in mask_text("aadhaar 2341 2341 2346")  # valid Verhoeff
    assert "[AADHAAR_1]" not in mask_text("aadhaar 2341 2341 2345")  # invalid checksum


def test_selective_disclosure_verifies_chosen_messages():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase_07"))
    from bundle_builder import build_bundle

    from packages.integrity.disclosure import disclose
    from packages.integrity.verify import verify_bundle

    full = build_bundle()
    partial = disclose(full.zip_bytes(), seqs=[1, 3, 5])
    r = verify_bundle(partial)
    assert r.verdict == "UNCHANGED"
    assert r.not_disclosed_count == len(full.leaves()) - 3


def test_anchoring_is_off_by_default_and_sends_only_a_hash(monkeypatch):
    from apps.api.settings import Settings
    from packages.integrity.anchoring import build_anchor_payload

    assert Settings(_env_file=None).anchor_enabled is False
    payload = build_anchor_payload(receipt_hash=bytes(32))
    assert set(payload) == {"hash"} and payload["hash"] == "00" * 32


def test_kannada_recap_requires_reviewed_templates():
    # FR-KAN-001: Kannada switches on only after native-speaker review, recorded by a REVIEWED file
    from pathlib import Path

    from packages.ingest.recap import kannada_available

    reviewed = Path(__file__).resolve().parents[2] / "playbooks" / "templates" / "kn" / "REVIEWED"
    assert kannada_available() is reviewed.is_file()


def test_integrity_red_flag_for_out_of_order_timestamps():
    from packages.ingest.whatsapp import parse_export
    from packages.intelligence.redflags import integrity_red_flags

    r = parse_export(b"14/10/26, 10:00 - Raju: a\n14/10/26, 09:00 - Meena: b\n")
    flags = integrity_red_flags(r.messages)
    assert flags and flags[0].kind == "out_of_order_timestamp"
    assert "fake" not in flags[0].reason_en.lower()
