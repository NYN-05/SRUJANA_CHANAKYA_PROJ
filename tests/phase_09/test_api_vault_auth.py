"""Phase 9: vault routes, session token and origin check (Architecture section 10; NFR-SEC-004; T16)."""

from __future__ import annotations

from api_support import PASS, TOKEN_HEADER


def test_setup_then_unlock(client):
    r = client.post("/api/vault/setup", json={"passphrase": PASS})
    assert r.status_code == 200 and len(r.json()["recovery_key"]) >= 24
    r = client.post("/api/vault/unlock", json={"passphrase": PASS})
    assert r.status_code == 200 and r.json()["token"]


def test_setup_twice_refused(client):
    client.post("/api/vault/setup", json={"passphrase": PASS})
    r = client.post("/api/vault/setup", json={"passphrase": "other"})
    assert r.status_code == 409


def test_wrong_passphrase_message(client):
    client.post("/api/vault/setup", json={"passphrase": PASS})
    r = client.post("/api/vault/unlock", json={"passphrase": "nope"})
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "wrong_passphrase"
    assert body["message_en"] == "That passphrase did not open the vault."


def test_recovery_key_unlock(client):
    rk = client.post("/api/vault/setup", json={"passphrase": PASS}).json()["recovery_key"]
    assert client.post("/api/vault/unlock", json={"recovery_key": rk}).status_code == 200


def test_token_required(api, client):
    assert client.get("/api/deals").status_code == 401
    assert client.get("/api/deals", headers={TOKEN_HEADER: "forged"}).status_code == 401
    assert api.get("/deals").status_code == 200


def test_lock_invalidates_token(api):
    assert api.post("/vault/lock").status_code == 200
    assert api.get("/deals").status_code == 401


def test_foreign_origin_refused(api):
    r = api.c.get("/api/deals", headers={**api.h, "Origin": "http://evil.example"})
    assert r.status_code == 403


def test_own_origin_allowed(api):
    r = api.c.get("/api/deals", headers={**api.h, "Origin": "http://127.0.0.1"})
    assert r.status_code == 200


def test_health_needs_no_token_and_leaks_nothing(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert set(r.json()) >= {"status", "safe_mode", "tier", "spec_version", "contract_version"}


def test_settings_bind_only_to_loopback(app_settings):
    assert app_settings.host in ("127.0.0.1", "localhost")
