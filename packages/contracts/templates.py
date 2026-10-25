"""Reads the fixed text templates in ``playbooks/templates/<lang>/``. Text lives in data, not code."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "playbooks" / "templates"
LANGUAGES = ("en", "hi")


@lru_cache(maxsize=None)
def load_yaml(lang: str, name: str) -> dict[str, Any]:
    """FileNotFoundError for an unknown language or file; ValueError when the file is not a mapping."""
    if lang not in LANGUAGES:
        raise FileNotFoundError(f"no templates for language {lang!r}")
    data = yaml.safe_load((TEMPLATES_DIR / lang / name).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} is not a mapping")
    return data
