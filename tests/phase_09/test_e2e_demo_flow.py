"""Phase 9: the demo flow end to end through the API, offline (AC-9.1, AC-9.2; PRD section 15)."""

from __future__ import annotations

import pytest
from bundle_helpers import change_one_char_in_message

from packages.integrity.verify import verify_bundle

pytestmark = pytest.mark.e2e
CLEAR = ("parties", "scope", "quantity", "price", "advance")


def run_demo(api):
    deal = api.import_sample("ambiguous")

    # live analysis: rules first
    events = api.stream_events(deal)
    flags = {(f["type"], f["term_key"]) for f in events[1]["data"]["flags"]}
    assert ("AMBIGUOUS_DATE", "delivery_date") in flags
    assert {("MISSING_TERM", "final_payment"), ("MISSING_TERM", "late_penalty")} <= flags

    for key in CLEAR:
        api.ok(api.post(f"/deals/{deal}/terms/{key}/confirm", {}))
    assert api.score(deal) == 55  # FR-SCO-001 worked example

    s = api.ok(api.get(f"/deals/{deal}/suggestion", params={"tone": "polite"}))
    assert s["target_term_keys"] == ["delivery_date", "final_payment"]

    # the user sets the real date, then sends the suggested message and the reply comes back
    api.ok(api.post(f"/deals/{deal}/terms/delivery_date/correct", {"value": {"kind": "date", "date": "2026-11-15"}}))
    text = api.ok(api.get(f"/deals/{deal}/suggestion", params={"tone": "polite"}))["text"]
    assert text == "Just to confirm, delivery by 15 Nov 2026 and the balance ₹48,000 on delivery, right?"
    api.ok(api.post(f"/deals/{deal}/messages", {"sender": "Raju", "text": text}))
    api.ok(api.post(f"/deals/{deal}/messages", {"sender": "Meena", "text": "haan theek hai"}))
    api.stream_events(deal)
    api.ok(api.post(f"/deals/{deal}/terms/final_payment/confirm", {}))
    assert api.score(deal) == 85  # 55 + delivery 15 + final payment 15; late penalty still missing

    # version, recap, echo-code confirmation
    api.ok(api.post(f"/deals/{deal}/versions", {}))
    recap = api.ok(api.post(f"/deals/{deal}/recap", {"language": "hi"}))
    api.ok(api.post(f"/deals/{deal}/recaps/{recap['id']}/approve", {}))
    reply = f"25/10/26, 10:00 - Meena: CONFIRM {recap['echo_code']}"
    assert api.ok(api.post(f"/deals/{deal}/recaps/{recap['id']}/check-reply", {"text": reply}))["state"] == "confirmed"

    # receipt and tamper test
    bundle = api.post(f"/deals/{deal}/export/bundle", {}).content
    assert verify_bundle(bundle).verdict == "UNCHANGED"
    tampered = verify_bundle(change_one_char_in_message(bundle, seq=2))
    assert tampered.verdict == "ALTERED"
    assert (tampered.first_difference.kind, tampered.first_difference.seq) == ("message", 2)
    return deal


def test_demo_flow(api):
    run_demo(api)


def test_demo_flow_with_network_blocked(api, block_network):
    run_demo(api)
