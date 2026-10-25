"""Phase 9: ingest routes (FR-IMP-001 to 009 through the API; S2)."""

from __future__ import annotations

PRIVACY = "This chat stays on this device. Nothing is uploaded."


def test_samples_listed(api):
    names = {s["name"] for s in api.ok(api.get("/ingest/samples"))["samples"]}
    assert {"clean", "ambiguous", "contradictory"} <= names


def test_preview_from_sample(api):
    p = api.ok(api.post("/ingest/preview", {"sample": "ambiguous"}))
    assert p["message_count"] == 5 and p["participants"] == ["Raju", "Meena"]
    assert p["date_order"] == "DMY" and p["needs_date_order_choice"] is False
    assert p["privacy_line"] == PRIVACY
    assert api.ok(api.get("/deals")) == {"deals": []}, "preview creates no deal"


def test_preview_from_file_upload(api, chat_bytes):
    r = api.c.post("/api/ingest/preview", headers=api.h, files={"file": ("WhatsApp Chat.txt", chat_bytes("clean.txt"), "text/plain")})
    assert r.status_code == 200 and r.json()["message_count"] == 6


def test_preview_from_pasted_text(api, chat_bytes):
    p = api.ok(api.post("/ingest/preview", {"text": chat_bytes("ambiguous.txt").decode()}))
    assert p["message_count"] == 5


def test_commit_creates_deal(api):
    deal = api.import_sample()
    deals = api.ok(api.get("/deals"))["deals"]
    assert [d["id"] for d in deals] == [deal]


def test_commit_needs_which_one_is_you(api):
    prev = api.ok(api.post("/ingest/preview", {"sample": "ambiguous"}))
    r = api.post("/ingest/commit", {"preview_id": prev["preview_id"], "counterparty": "Meena", "playbook_key": "supply_order"})
    assert r.status_code in (400, 422)


def test_unreadable_file_message(api):
    r = api.c.post("/api/ingest/preview", headers=api.h, files={"file": ("x.bin", bytes(range(256)) * 20, "application/octet-stream")})
    assert r.status_code == 400
    body = r.json()
    assert body["message_en"] == "We could not read this file. Choose the exported .txt or .zip."
    assert body["message_hi"] and body["hint"]


def test_too_large_is_413(api, monkeypatch):
    big = b"14/10/26, 09:00 - Raju: " + b"x" * (25 * 1024 * 1024) + b"\n"
    r = api.c.post("/api/ingest/preview", headers=api.h, files={"file": ("big.txt", big, "text/plain")})
    assert r.status_code == 413


def test_unknown_preview_id(api):
    r = api.post("/ingest/commit", {"preview_id": "nope", "me": "Raju", "counterparty": "Meena", "playbook_key": "supply_order"})
    assert r.status_code == 404


def test_simulator_message_is_stored_with_origin(api):
    deal = api.import_sample()
    m = api.ok(api.post(f"/deals/{deal}/messages", {"sender": "Meena", "text": "delivery next week"}))
    assert m["origin"] == "simulator" and m["seq"] == 6
