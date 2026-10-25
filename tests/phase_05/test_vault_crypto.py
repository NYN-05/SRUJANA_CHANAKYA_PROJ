"""Phase 5: vault encryption and recovery (FR-VLT-005, NFR-SEC-001, THREAT_MODEL T11, T12)."""

from __future__ import annotations

import pytest

from packages.vault import Vault, VaultLocked, WrongPassphrase

CANARY = "UNIQUE-CANARY-7731-ठीक"


def _draft_with(text):
    from packages.contracts import MessageOrigin
    from packages.ingest.commit import prepare_commit
    from packages.ingest.whatsapp import parse_export

    raw = f"13/10/26, 10:00 - Raju: {text}\n13/10/26, 10:01 - Meena: ok\n".encode()
    return raw, prepare_commit(parse_export(raw), me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)


def all_bytes_under(folder):
    return b"".join(p.read_bytes() for p in folder.rglob("*") if p.is_file())


def test_create_returns_recovery_key(tmp_path, fast_kdf):
    v, rk = Vault.create(tmp_path / "v", "pass-one", kdf=fast_kdf)
    assert isinstance(rk, str) and len(rk) >= 24
    v.lock()


def test_create_refuses_existing_vault(tmp_path, fast_kdf):
    v, _ = Vault.create(tmp_path / "v", "pass-one", kdf=fast_kdf)
    v.lock()
    with pytest.raises(FileExistsError):
        Vault.create(tmp_path / "v", "pass-two", kdf=fast_kdf)


def test_wrong_passphrase(tmp_path, fast_kdf):
    v, _ = Vault.create(tmp_path / "v", "right", kdf=fast_kdf)
    v.lock()
    with pytest.raises(WrongPassphrase):
        Vault.unlock(tmp_path / "v", passphrase="wrong")


def test_unlock_with_passphrase_reads_data(tmp_path, fast_kdf):
    v, _ = Vault.create(tmp_path / "v", "right", kdf=fast_kdf)
    raw, draft = _draft_with("hello")
    deal = v.commit_import(draft, export_bytes=raw, file_name="c.txt", media={})
    v.lock()
    v2 = Vault.unlock(tmp_path / "v", passphrase="right")
    assert [m.text for m in v2.messages(deal)] == ["hello", "ok"]
    v2.lock()


def test_recovery_key_opens_and_sets_new_passphrase(tmp_path, fast_kdf):
    v, rk = Vault.create(tmp_path / "v", "old-pass", kdf=fast_kdf)
    v.lock()
    v2 = Vault.unlock(tmp_path / "v", recovery_key=rk)
    v2.change_passphrase("new-pass")
    v2.lock()
    Vault.unlock(tmp_path / "v", passphrase="new-pass").lock()
    with pytest.raises(WrongPassphrase):
        Vault.unlock(tmp_path / "v", passphrase="old-pass")
    Vault.unlock(tmp_path / "v", recovery_key=rk).lock()  # recovery key still works


def test_wrong_recovery_key(tmp_path, fast_kdf):
    v, rk = Vault.create(tmp_path / "v", "p", kdf=fast_kdf)
    v.lock()
    with pytest.raises(WrongPassphrase):
        Vault.unlock(tmp_path / "v", recovery_key=rk[:-1] + ("A" if rk[-1] != "A" else "B"))


def test_locked_vault_refuses_reads(tmp_path, fast_kdf):
    v, _ = Vault.create(tmp_path / "v", "p", kdf=fast_kdf)
    v.lock()
    with pytest.raises(VaultLocked):
        v.deals()


def test_no_plaintext_on_disk(tmp_path, fast_kdf):
    v, _ = Vault.create(tmp_path / "v", "p", kdf=fast_kdf)
    raw, draft = _draft_with(f"price {CANARY} 480 each")
    v.commit_import(draft, export_bytes=raw, file_name=f"{CANARY}.txt", media={"note.opus": CANARY.encode() * 10})
    blob = all_bytes_under(tmp_path / "v")
    v.lock()
    blob += all_bytes_under(tmp_path / "v")
    for needle in (CANARY.encode("utf-8"), "UNIQUE-CANARY-7731".encode("utf-16-le"), b"Raju", b"Meena"):
        assert needle not in blob, f"plaintext found on disk: {needle!r}"


def test_passphrase_never_stored(tmp_path, fast_kdf):
    v, rk = Vault.create(tmp_path / "v", "a-very-distinct-passphrase", kdf=fast_kdf)
    v.lock()
    blob = all_bytes_under(tmp_path / "v")
    assert b"a-very-distinct-passphrase" not in blob
    assert rk.encode() not in blob


def test_kdf_parameters_recorded_in_header(tmp_path, fast_kdf):
    v, _ = Vault.create(tmp_path / "v", "p", kdf=fast_kdf)
    assert v.kdf_params() == fast_kdf
    v.lock()
