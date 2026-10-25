"""Phase 0: models/manifest.json holds names and hashes only (ADR-008, NFR-SEC-002)."""

from __future__ import annotations

import json
import re


def _manifest(project_root):
    return json.loads((project_root / "models" / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_is_object_with_models_list(project_root):
    data = _manifest(project_root)
    assert isinstance(data, dict)
    assert isinstance(data.get("models"), list)


def test_every_entry_has_valid_fields(project_root):
    for entry in _manifest(project_root)["models"]:
        assert set(entry) >= {"name", "role", "tier", "file", "size_bytes", "sha256"}, entry
        assert entry["role"] in {"extraction", "speech"}
        assert entry["tier"] in {"high", "default", "low", "small", "base"}
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), entry["name"]
        assert isinstance(entry["size_bytes"], int) and entry["size_bytes"] > 0
        assert "/" not in entry["file"] and "\\" not in entry["file"], "file is a bare name inside VERIDOC_MODEL_DIR"


def test_manifest_contains_no_weights_or_urls_with_credentials(project_root):
    raw = (project_root / "models" / "manifest.json").read_text(encoding="utf-8")
    assert len(raw) < 100_000, "the manifest lists names and hashes only"
    assert not re.search(r"https?://[^/\s]*:[^@\s]*@", raw), "no credentials in URLs"
