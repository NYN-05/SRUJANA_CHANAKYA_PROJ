"""Phase 9: live analysis, term actions and suggestions (FR-SCO-003, FR-SUG-001 to 004, FR-AIS-005; S3, S4)."""

from __future__ import annotations

import time

import pytest


@pytest.fixture
def deal(api):
    return api.import_sample()


def test_stream_event_order(api, deal):
    events = api.stream_events(deal)
    names = [e["event"] for e in events]
    assert names[:4] == ["terms", "flags", "score", "suggestion"], "rules results first"
    assert names[-1] == "done"
    terms = {t["key"]: t for t in events[0]["data"]["terms"]}
    assert terms["delivery_date"]["state"] == "unclear"
    assert terms["final_payment"]["state"] == "missing"
    flag_types = {(f["type"], f["term_key"]) for f in events[1]["data"]["flags"]}
    assert ("AMBIGUOUS_DATE", "delivery_date") in flag_types
    assert ("MISSING_TERM", "final_payment") in flag_types and ("MISSING_TERM", "late_penalty") in flag_types


def test_status_words_with_symbols_in_payload(api, deal):
    terms = api.stream_events(deal)[0]["data"]["terms"]
    labels = {t["state"]: t["label"] for t in terms}
    assert labels["stated"] == "✓ Clear" and labels["unclear"] == "! Ambiguous" and labels["missing"] == "○ Missing"


def test_confirm_returns_term_and_score_change(api, deal):
    r = api.ok(api.post(f"/deals/{deal}/terms/price/confirm", {}))
    assert r["term"]["key"] == "price"
    assert r["score_after"] > r["score_before"]


def test_confirm_unclear_without_value_is_409(api, deal):
    r = api.post(f"/deals/{deal}/terms/delivery_date/confirm", {})
    assert r.status_code == 409 and r.json()["code"] == "term_not_confirmable"


def test_correct_then_confirmed(api, deal):
    r = api.ok(api.post(f"/deals/{deal}/terms/delivery_date/correct", {"value": {"kind": "date", "date": "2026-11-15"}}))
    assert r["term"]["origin"] == "user"


def test_invalid_corrected_value_is_422(api, deal):
    r = api.post(f"/deals/{deal}/terms/delivery_date/correct", {"value": {"kind": "date", "date": "15/11/2026"}})
    assert r.status_code == 422


def test_reject(api, deal):
    api.ok(api.post(f"/deals/{deal}/terms/price/confirm", {}))
    api.ok(api.post(f"/deals/{deal}/terms/price/reject", {}))


def test_suggestion_tones(api, deal):
    texts = {}
    for tone in ("casual", "polite", "firm"):
        s = api.ok(api.get(f"/deals/{deal}/suggestion", params={"tone": tone}))
        assert s["target_term_keys"] == ["delivery_date", "final_payment"]
        texts[tone] = s["text"]
    assert len(set(texts.values())) == 3


def test_suggestion_copied_is_recorded_and_never_sent(api, deal):
    s = api.ok(api.get(f"/deals/{deal}/suggestion", params={"tone": "polite"}))
    r = api.ok(api.post(f"/deals/{deal}/suggestion/copied", {"text": s["text"]}))
    assert r == {"copied": True, "sent": False}


def test_bad_tone_is_422(api, deal):
    assert api.get(f"/deals/{deal}/suggestion", params={"tone": "angry"}).status_code == 422


def test_safe_mode_toggle_takes_effect_without_restart(api, deal):
    api.ok(api.post("/settings", {"safe_mode": True}))
    events = api.stream_events(deal)
    assert "terms_refined" not in [e["event"] for e in events]
    assert api.ok(api.get("/health"))["safe_mode"] is True
    api.ok(api.post("/settings", {"safe_mode": False}))
    assert api.ok(api.get("/health"))["safe_mode"] is False


def test_simulator_message_triggers_rules_result_quickly(api, deal):
    start = time.perf_counter()
    api.ok(api.post(f"/deals/{deal}/messages", {"sender": "Raju", "text": "approx 50k for the next lot"}))
    events = api.stream_events(deal)
    assert time.perf_counter() - start < 5
    assert any(f["type"] == "AMBIGUOUS_AMOUNT" for f in events[1]["data"]["flags"])


def test_unknown_deal_is_404(api):
    assert api.get("/deals/00000000-0000-4000-8000-000000000000/score").status_code == 404
