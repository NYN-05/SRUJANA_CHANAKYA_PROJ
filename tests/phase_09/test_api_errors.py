"""Phase 9: one error body shape, no tracebacks (Architecture section 11)."""

from __future__ import annotations

import pytest

SHAPE = {"code", "message_en", "message_hi", "hint"}


def check(resp, status):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == SHAPE, body
    assert body["message_en"] and body["message_hi"] and body["hint"]
    for marker in ("Traceback", 'File "', "Exception", "packages/", "packages\\"):
        assert marker not in resp.text


def test_401_shape(client):
    check(client.get("/api/deals"), 401)


def test_404_shape(api):
    check(api.get("/deals/00000000-0000-4000-8000-000000000000/receipt"), 404)


def test_409_shape(api):
    d = api.import_sample()
    check(api.post(f"/deals/{d}/terms/final_payment/confirm", {}), 409)


def test_422_shape(api):
    d = api.import_sample()
    check(api.post(f"/deals/{d}/terms/price/correct", {"value": {"kind": "money", "paise": "-5"}}), 422)


def test_unexpected_error_is_internal_without_trace(api):
    from fastapi.testclient import TestClient

    app = api.c.app

    @app.get("/api/test-only-boom")
    def boom():
        raise RuntimeError("secret detail 200 shirts")

    quiet = TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False)
    r = quiet.get("/api/test-only-boom", headers=api.h)
    check(r, 500)
    assert r.json()["code"] == "internal"
    assert "secret detail" not in r.text


@pytest.mark.parametrize("path", ["/deals/x/terms/price/confirm", "/deals/x/recap"])
def test_bad_ids_never_500(api, path):
    assert api.post(path, {}).status_code in (404, 422)
