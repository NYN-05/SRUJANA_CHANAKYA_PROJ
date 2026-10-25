"""Fixed text templates in ``playbooks/templates/<lang>/`` (flags and suggestions). Text lives in data, not code."""

from __future__ import annotations

from typing import Any

from packages.contracts.templates import LANGUAGES, TEMPLATES_DIR
from packages.contracts.templates import load_yaml as _load_yaml

__all__ = ["LANGUAGES", "TEMPLATES_DIR", "TemplateMissing", "load_yaml"]


class TemplateMissing(Exception):
    """No template for a gap. A build-time test checks every gap has one, so a user never sees this."""

    def __init__(self, key: str, tone: str | None, lang: str) -> None:
        super().__init__(f"no template for {key!r} (tone {tone!r}, language {lang!r})")
        self.key, self.tone, self.lang = key, tone, lang


def load_yaml(lang: str, name: str) -> dict[str, Any]:
    try:
        return _load_yaml(lang, name)
    except (FileNotFoundError, ValueError) as exc:
        raise TemplateMissing(name, None, lang) from exc
