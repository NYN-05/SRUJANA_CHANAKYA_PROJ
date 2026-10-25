"""The three synthetic sample chats (FR-IMP-007). Gold labels live in eval/labels/sample_<name>.json."""

from __future__ import annotations

from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"


def list_samples() -> list[str]:
    return sorted(p.stem for p in SAMPLES_DIR.glob("*.txt"))


def load_sample(name: str) -> bytes:
    """Raw bytes of a sample export. Only listed names are accepted, so no path is ever built from input."""
    if name not in list_samples():
        raise KeyError(name)
    return (SAMPLES_DIR / f"{name}.txt").read_bytes()
