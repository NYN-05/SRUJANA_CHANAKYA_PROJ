"""Phase 8: model file check, tiers and safe mode (NFR-SEC-002, FR-SAF-001, FR-AIS-005, AI_SPEC sections 9 and 11)."""

from __future__ import annotations

import hashlib

import pytest

from packages.intelligence.model.models import ModelStatus, analysis_mode, select_tier, verify_model_file

THRESHOLDS = {"high": 16, "default": 8, "low": 4}


def entry_for(path, data):
    return {"name": "test-model", "role": "extraction", "tier": "default", "file": path.name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_matching_hash(tmp_path):
    data = b"GGUF" + bytes(range(256)) * 1000
    p = tmp_path / "m.gguf"
    p.write_bytes(data)
    assert verify_model_file(p, entry_for(p, data)) is True


def test_mismatched_hash(tmp_path):
    data = b"GGUF" + bytes(1000)
    p = tmp_path / "m.gguf"
    p.write_bytes(data)
    e = entry_for(p, data)
    p.write_bytes(data + b"\x00")
    assert verify_model_file(p, e) is False


def test_missing_file(tmp_path):
    assert verify_model_file(tmp_path / "absent.gguf", {"sha256": "0" * 64, "size_bytes": 1, "file": "absent.gguf"}) is False


@pytest.mark.parametrize(
    "ram,avx2,tier",
    [(32, True, "high"), (16, True, "high"), (15.5, True, "default"), (8, True, "default"), (7.8, True, "low"), (4, True, "low"), (3.9, True, "safe"), (16, False, "low"), (3, False, "safe")],
)
def test_select_tier(ram, avx2, tier):
    assert select_tier(ram, avx2, THRESHOLDS) == tier


@pytest.mark.parametrize(
    "switch,status,expected",
    [
        (True, ModelStatus(present=True, hash_ok=True, load_failures=0, tier="default"), ("rules_only", "switch")),
        (False, ModelStatus(present=True, hash_ok=False, load_failures=0, tier="default"), ("rules_only", "hash_mismatch")),
        (False, ModelStatus(present=True, hash_ok=True, load_failures=2, tier="default"), ("rules_only", "load_failed")),
        (False, ModelStatus(present=True, hash_ok=True, load_failures=1, tier="default"), ("rules_and_ai", None)),
        (False, ModelStatus(present=True, hash_ok=True, load_failures=0, tier="safe"), ("rules_only", "low_hardware")),
        (False, ModelStatus(present=False, hash_ok=None, load_failures=0, tier="default"), ("rules_only", "model_missing")),
        (False, ModelStatus(present=True, hash_ok=True, load_failures=0, tier="default"), ("rules_and_ai", None)),
    ],
)
def test_analysis_mode(switch, status, expected):
    assert analysis_mode(switch, status) == expected


def test_size_mismatch_fails_before_hashing(tmp_path):
    data = b"GGUF" + bytes(500)
    p = tmp_path / "m.gguf"
    p.write_bytes(data)
    assert verify_model_file(p, dict(entry_for(p, data), size_bytes=len(data) + 1)) is False


def test_entry_without_a_hash_never_matches(tmp_path):
    p = tmp_path / "m.gguf"
    p.write_bytes(b"x")
    assert verify_model_file(p, {"file": "m.gguf"}) is False


def test_an_unchecked_model_is_not_a_mismatch():
    assert analysis_mode(False, ModelStatus(present=True, hash_ok=None, load_failures=0, tier="low")) == ("rules_and_ai", None)


def test_the_switch_is_read_on_every_call():
    status = ModelStatus(present=True, hash_ok=True, load_failures=0, tier="default")
    assert [analysis_mode(s, status)[0] for s in (False, True, False)] == ["rules_and_ai", "rules_only", "rules_and_ai"]


def test_switch_wins_over_every_other_reason():
    assert analysis_mode(True, ModelStatus(present=False, hash_ok=False, load_failures=5, tier="safe"))[1] == "switch"
