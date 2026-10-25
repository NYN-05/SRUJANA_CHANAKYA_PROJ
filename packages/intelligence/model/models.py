"""The model file check, hardware tiers and the safe-mode decision (NFR-SEC-002, FR-SAF-001, FR-AIS-005, AI_SPEC 9 and 11).

``analysis_mode`` is a pure function of the switch and the status, and callers read the switch on every analysis call,
so turning safe mode on takes effect without a restart.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ModelStatus:
    present: bool
    hash_ok: bool | None  # None until the file was checked
    load_failures: int
    tier: str  # high | default | low | safe


def verify_model_file(path: str | Path, entry: Mapping[str, Any]) -> bool:
    """True only when the file exists and its size and streamed SHA-256 match the manifest entry."""
    path = Path(path)
    try:
        if "size_bytes" in entry and path.stat().st_size != entry["size_bytes"]:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(CHUNK):
                digest.update(chunk)
    except OSError:
        return False
    return digest.hexdigest() == entry.get("sha256")


def select_tier(ram_gb: float, has_avx2: bool, thresholds: Mapping[str, float]) -> str:
    """The largest tier whose RAM threshold is met; a CPU without AVX2 is capped at ``low``."""
    tier = next((name for name in ("high", "default", "low") if ram_gb >= thresholds[name]), "safe")
    return "low" if tier in ("high", "default") and not has_avx2 else tier


def analysis_mode(safe_mode_switch: bool, status: ModelStatus) -> tuple[str, str | None]:
    """``(mode, reason)``: ``rules_only`` with the first reason that applies, in priority order, or ``rules_and_ai``."""
    if safe_mode_switch:
        return "rules_only", "switch"
    if not status.present:
        return "rules_only", "model_missing"
    if status.hash_ok is False:
        return "rules_only", "hash_mismatch"
    if status.load_failures >= 2:
        return "rules_only", "load_failed"
    if status.tier == "safe":
        return "rules_only", "low_hardware"
    return "rules_and_ai", None
