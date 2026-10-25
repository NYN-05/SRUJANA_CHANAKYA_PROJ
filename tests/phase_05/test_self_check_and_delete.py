"""Phase 5: startup self-check and deal deletion (NFR-REL-002, NFR-PRV-003, Data Model sections 6 and 7)."""

from __future__ import annotations

import hashlib

import pytest
from helpers import commit_sample

AUDIO = b"OggS" + b"voice" * 200


def test_self_check_passes_on_a_healthy_vault(vault):
    commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    results = vault.self_check()
    names = {r.name for r in results}
    assert {"integrity_check", "triggers", "insert_only_probe", "evidence"} <= names
    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_tampered_evidence_file_is_named(vault):
    commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    digest = hashlib.sha256(AUDIO).hexdigest()
    path = vault.evidence_path(digest)
    data = bytearray(path.read_bytes())
    data[-1] ^= 0x01
    path.write_bytes(bytes(data))
    bad = [r for r in vault.self_check() if not r.ok]
    assert bad and any(digest in r.detail for r in bad)


def test_missing_evidence_file_is_reported(vault):
    commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    vault.evidence_path(hashlib.sha256(AUDIO).hexdigest()).unlink()
    assert not all(r.ok for r in vault.self_check())


def test_delete_deal_crypto_shreds(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    path = vault.evidence_path(hashlib.sha256(AUDIO).hexdigest())
    vault.delete_deal(deal)
    assert deal not in {d.id for d in vault.deals()}
    assert not path.exists()
    with pytest.raises(KeyError):
        vault.messages(deal)
    last = vault.audit_events(None)[-1]
    assert last.action == "delete_deal" and last.deal_id == deal
    assert "Raju" not in str(last.detail) and "shirts" not in str(last.detail)
    assert all(r.ok for r in vault.self_check())


def test_delete_one_deal_keeps_others(vault):
    d1, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    d2, _ = commit_sample(vault, "clean.txt", "Anita", "Rohit")
    vault.delete_deal(d1)
    assert [m.text for m in vault.messages(d2)][0].startswith("Hi, need 500 banners")
