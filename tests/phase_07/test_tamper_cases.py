"""Phase 7: the seven tamper cases of INTEGRITY_SPEC section 11, plus the import record (I-09)."""

from __future__ import annotations

import pytest
from bundle_builder import (
    build_bundle,
    tamper_change_message,
    tamper_change_transcript,
    tamper_edit_version,
    tamper_import_record,
    tamper_remove_message,
    tamper_replace_audio,
    tamper_swap_messages,
    tamper_truncate_chain,
)

from packages.integrity.verify import verify_bundle

# leaves: 1-8 messages, 9 audio, 10 transcript span, 11-13 term leaves of versions 1-3
CASES = [
    ("changed_message", tamper_change_message, ("message", 7, None)),
    ("removed_message", tamper_remove_message, ("message", 5, None)),
    ("swapped_messages", tamper_swap_messages, ("message", 3, None)),
    ("replaced_audio", tamper_replace_audio, ("voice_audio", 9, None)),
    ("changed_transcript", tamper_change_transcript, ("transcript_span", 10, None)),
    ("edited_version", tamper_edit_version, ("chain_link", None, 1)),
    ("truncated_chain", tamper_truncate_chain, ("chain_link", None, 3)),
    ("changed_import_record", tamper_import_record, ("import_record", None, None)),
]


def test_untampered_bundle_is_unchanged():
    r = verify_bundle(build_bundle().zip_bytes())
    assert r.verdict == "UNCHANGED", r
    assert r.first_difference is None


@pytest.mark.parametrize("name,tamper,expected", CASES, ids=[c[0] for c in CASES])
def test_tamper_case_detected_with_first_item(name, tamper, expected):
    r = verify_bundle(tamper(build_bundle()).zip_bytes())
    assert r.verdict == "ALTERED", name
    fd = r.first_difference
    assert (fd.kind, fd.seq, fd.version_n) == expected, name


def test_message_seven_case_also_reports_root_mismatch():
    r = verify_bundle(tamper_change_message(build_bundle(), 7).zip_bytes())
    checks = {c.name: c for c in r.checks}
    assert checks["leaves"].ok is False
    assert checks["merkle_root"].ok is False


def test_two_changes_report_the_lowest_sequence():
    b = tamper_change_message(tamper_change_message(build_bundle(), 6), 2)
    assert verify_bundle(b.zip_bytes()).first_difference.seq == 2


def test_leaf_change_wins_over_chain_change():
    b = tamper_edit_version(tamper_change_message(build_bundle(), 8), 1)
    assert verify_bundle(b.zip_bytes()).first_difference.kind == "message"


def test_receipt_body_edit_is_altered():
    b = build_bundle()
    env = b.json("receipt.json")
    env["body"]["leaf_count"] += 1
    b.set_json("receipt.json", env)
    assert verify_bundle(b.zip_bytes()).verdict == "ALTERED"


def test_leaf_with_only_a_hash_is_taken_as_given():
    b = build_bundle()
    rows = b.leaves()
    for r in rows:
        if r["seq"] == 2:
            r["salt"] = r["payload_digest"] = r["payload"] = None
    b.set_leaves(rows)
    assert verify_bundle(b.zip_bytes()).verdict == "UNCHANGED"


def test_audio_not_exported_is_taken_as_given():
    b = build_bundle()
    for name in [n for n in b.files if n.startswith("media/")]:
        del b.files[name]
    rows = b.leaves()
    for r in rows:
        if r["kind"] == "voice_audio":
            r["payload_file"] = None
    b.set_leaves(rows)
    assert verify_bundle(b.zip_bytes()).verdict == "UNCHANGED"


def test_disclosed_leaf_with_hash_changed_to_match_is_still_caught_by_root():
    # attacker edits text AND recomputes that leaf: the root no longer matches
    from packages.integrity.hashing import TypeByte, leaf_hash, payload_digest_json

    b = build_bundle()
    rows = b.leaves()
    r = next(x for x in rows if x["seq"] == 7)
    r["payload"]["text"] = "price 1 each"
    digest = payload_digest_json(r["payload"])
    r["payload_digest"] = digest.hex()
    r["leaf_hash"] = leaf_hash(TypeByte.MESSAGE, bytes.fromhex(r["salt"]), digest).hex()
    b.set_leaves(rows)
    res = verify_bundle(b.zip_bytes())
    assert res.verdict == "ALTERED"
    assert {c.name: c.ok for c in res.checks}["merkle_root"] is False
