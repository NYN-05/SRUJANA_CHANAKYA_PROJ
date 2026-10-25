"""Phase 9 fixtures: an app on a fresh vault, unlocked, with the model in fake mode."""

from __future__ import annotations

import json

import pytest
from api_support import PASS, TOKEN_HEADER


class Api:
    def __init__(self, client, token):
        self.c = client
        self.h = {TOKEN_HEADER: token}

    def get(self, path, **kw):
        return self.c.get(f"/api{path}", headers=self.h, **kw)

    def post(self, path, json_body=None, **kw):
        return self.c.post(f"/api{path}", headers=self.h, json=json_body, **kw)

    def ok(self, resp, status=200):
        assert resp.status_code == status, resp.text
        return resp.json()

    # --- flow helpers ------------------------------------------------------
    def import_sample(self, name="ambiguous", me="Raju", cp="Meena", playbook="supply_order"):
        prev = self.ok(self.post("/ingest/preview", {"sample": name}))
        body = {"preview_id": prev["preview_id"], "me": me, "counterparty": cp, "playbook_key": playbook}
        return self.ok(self.post("/ingest/commit", body))["deal_id"]

    def stream_events(self, deal_id):
        events, current = [], {}
        with self.c.stream("GET", f"/api/deals/{deal_id}/analysis/stream", headers=self.h) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    current["event"] = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    current["data"] = json.loads(line.split(":", 1)[1].strip())
                elif not line and current:
                    events.append(current)
                    if current.get("event") == "done":
                        break
                    current = {}
        return events

    def score(self, deal_id):
        return self.ok(self.get(f"/deals/{deal_id}/score"))["score"]


@pytest.fixture
def app_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("VERIDOC_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VERIDOC_MODEL_MODE", "fake")
    monkeypatch.setenv("VERIDOC_SAFE_MODE", "0")
    monkeypatch.setenv("VERIDOC_KDF_TEST_PARAMS", "1")  # small Argon2id values for tests only (Q-23)
    from apps.api.settings import Settings

    return Settings(_env_file=None)


@pytest.fixture
def client(app_settings):
    from fastapi.testclient import TestClient

    from apps.api.main import create_app

    with TestClient(create_app(app_settings), base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture
def api(client):
    r = client.post("/api/vault/setup", json={"passphrase": PASS})
    assert r.status_code == 200, r.text
    assert r.json()["recovery_key"]
    r = client.post("/api/vault/unlock", json={"passphrase": PASS})
    assert r.status_code == 200, r.text
    return Api(client, r.json()["token"])
