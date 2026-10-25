"""Phase 9: recap, reply check, versions, receipt and bundle through the API (S6, S7, S8, S12)."""

from __future__ import annotations

import io
import zipfile

import pytest

from packages.integrity.verify import verify_bundle

CLEAR = ("parties", "scope", "quantity", "price", "advance")


@pytest.fixture
def deal(api):
    d = api.import_sample()
    for key in CLEAR:
        api.ok(api.post(f"/deals/{d}/terms/{key}/confirm", {}))
    api.ok(api.post(f"/deals/{d}/terms/delivery_date/correct", {"value": {"kind": "date", "date": "2026-11-15"}}))
    api.ok(api.post(f"/deals/{d}/versions", {}))
    return d


def test_recap_english(api, deal):
    r = api.ok(api.post(f"/deals/{deal}/recap", {"language": "en"}))
    assert r["text"].startswith("Hi Meena, just confirming what we discussed:")
    assert r["text"].endswith(f"If all correct, reply: CONFIRM {r['echo_code']}")
    assert {o["key"] for o in r["omitted_terms"]} == {"final_payment", "late_penalty"}
    assert r["disclaimer"] == "Drafting aid, not legal advice. Please read each line before confirming."


def test_recap_hindi(api, deal):
    r = api.ok(api.post(f"/deals/{deal}/recap", {"language": "hi"}))
    assert "नमस्ते" in r["text"] and f"CONFIRM {r['echo_code']}" in r["text"]


def test_kannada_not_in_this_build(api, deal):
    r = api.post(f"/deals/{deal}/recap", {"language": "kn"})
    assert r.status_code == 422


def test_reply_check_flow(api, deal):
    r = api.ok(api.post(f"/deals/{deal}/recap", {"language": "en"}))
    bad = api.ok(api.post(f"/deals/{deal}/recaps/{r['id']}/check-reply", {"text": "CONFIRM ZZZZ", "sender": "Meena"}))
    assert bad["state"] == "not_confirmed" and bad["message_en"] == "code does not match this recap"
    api.ok(api.post(f"/deals/{deal}/recaps/{r['id']}/approve", {}))
    good = api.ok(api.post(f"/deals/{deal}/recaps/{r['id']}/check-reply", {"text": f"confirm {r['echo_code'].lower()}", "sender": "Meena"}))
    assert good["state"] == "confirmed"
    versions = api.ok(api.get(f"/deals/{deal}/versions"))["versions"]
    assert versions[-1]["confirmed"] is True


def test_versions_and_diff(api, deal):
    api.ok(api.post(f"/deals/{deal}/terms/delivery_date/correct", {"value": {"kind": "date", "date": "2026-11-22"}}))
    api.ok(api.post(f"/deals/{deal}/versions", {}))
    diff = api.ok(api.get(f"/deals/{deal}/versions/diff", params={"a": 1, "b": 2}))["rows"]
    changed = [r["key"] for r in diff if r["change"] != "no_change"]
    assert changed == ["delivery_date"]


def test_version_with_nothing_confirmed_is_409(api):
    d = api.import_sample()
    r = api.post(f"/deals/{d}/versions", {})
    assert r.status_code == 409 and r.json()["code"] == "nothing_to_version"


def test_receipt(api, deal):
    r = api.ok(api.get(f"/deals/{deal}/receipt"))
    assert set(r["body"]) >= {"spec_version", "root", "chain", "recorded_at", "import_record_hash"}
    assert r["limit_text"] == "This checks that the record was not changed after it was saved. It cannot prove that the original chat export was genuine."
    assert r["clock_note"] == "The time shown comes from this device's clock. It can be wrong until the record is anchored."


def test_bundle_export_verifies(api, deal):
    resp = api.post(f"/deals/{deal}/export/bundle", {})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert resp.headers.get("X-VeriDoc-Warning") == "Exported files are not encrypted. Share them only with people you trust."
    data = resp.content
    zipfile.ZipFile(io.BytesIO(data)).testzip()
    assert verify_bundle(data).verdict == "UNCHANGED"
