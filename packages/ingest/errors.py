"""Typed import refusals (FR-IMP-003). User-facing text comes from the API layer (Phase 9)."""

from __future__ import annotations

REFUSAL_CODES = frozenset({"empty", "binary", "too_large", "not_whatsapp", "bad_zip", "no_chat_file", "zip_limits"})


class ImportRefused(Exception):
    """The input is refused as a whole; nothing is created."""

    def __init__(self, code: str) -> None:
        if code not in REFUSAL_CODES:
            raise ValueError(f"unknown refusal code {code!r}")
        super().__init__(code)
        self.code = code
