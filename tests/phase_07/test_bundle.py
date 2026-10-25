"""Phase 7: bundles exported by the vault follow Appendix D and verify (FR-VFY-003, FR-VFY-005)."""

from __future__ import annotations

import json
import zipfile

import pytest
from bundle_builder import Bundle, tamper_change_message
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue
from packages.integrity.verify import verify_bundle

LIMIT = "This checks that the record was not changed after it was saved. It cannot prove that the original chat export was genuine."
AUDIO = b"OggS" + b"note" * 300


@pytest.fixture
def deal(vault):
    deal_id, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    confirm_clear_terms(vault, deal_id)
    vault.correct_term(deal_id, "delivery_date", DateValue(date="2026-11-15"))
    vault.create_version(deal_id)
    return deal_id


def test_bundle_members(vault, deal, tmp_path):
    path = vault.export_bundle(deal, tmp_path)
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert {"receipt.json", "leaves.jsonl", "chain.json", "import_record.json", "README.txt"} <= names
        assert not any(n.startswith("media/") for n in names), "media only when asked"
        readme = z.read("README.txt").decode("utf-8")
        assert LIMIT in readme
        rows = [json.loads(line) for line in z.read("leaves.jsonl").decode("utf-8").splitlines() if line]
    assert [r["seq"] for r in rows] == list(range(1, len(rows) + 1))
    for r in rows:
        assert set(r) == {"seq", "type_byte", "kind", "leaf_hash", "salt", "payload_digest", "payload", "payload_file"}


def test_fresh_bundle_verifies(vault, deal, tmp_path):
    assert verify_bundle(vault.export_bundle(deal, tmp_path)).verdict == "UNCHANGED"


def test_bundle_with_media_verifies_audio(vault, deal, tmp_path):
    path = vault.export_bundle(deal, tmp_path, include_media=True)
    with zipfile.ZipFile(path) as z:
        assert any(n.startswith("media/") for n in z.namelist())
    assert verify_bundle(path).verdict == "UNCHANGED"


def test_one_character_change_in_exported_message_is_named(vault, deal, tmp_path):
    data = vault.export_bundle(deal, tmp_path).read_bytes()
    tampered = tamper_change_message(Bundle.from_zip(data), seq=4)
    r = verify_bundle(tampered.zip_bytes())
    assert r.verdict == "ALTERED"
    assert (r.first_difference.kind, r.first_difference.seq) == ("message", 4)


def test_export_does_not_leave_partial_files_on_failure(vault, deal, tmp_path):
    out = tmp_path / "readonly"
    out.mkdir()
    target = out / "not-a-dir"
    target.write_text("x")
    with pytest.raises((OSError, ValueError)):
        vault.export_bundle(deal, target)
    assert sorted(p.name for p in out.iterdir()) == ["not-a-dir"]


def test_export_is_audited(vault, deal, tmp_path):
    vault.export_bundle(deal, tmp_path)
    assert vault.audit_events(deal)[-1].action == "export"
