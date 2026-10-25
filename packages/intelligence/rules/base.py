"""Shared pieces of the rules parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Boundaries that also work next to Devanagari and Kannada letters, where \w skips the vowel signs.
NOT_AFTER = r"(?<![A-Za-z0-9\u0900-\u0DFF])"
NOT_BEFORE = r"(?![A-Za-z\u0900-\u0DFF])"
NUM_START = r"(?<![\w:/#.])"  # a number does not start inside a time, a date, a tag or another number


@dataclass(frozen=True, kw_only=True)
class Match:
    start: int  # span in the ORIGINAL text
    end: int
    raw: str


def alternation(words: list[str] | tuple[str, ...]) -> str:
    """Longest-first regex alternation of literal words."""
    return "|".join(re.escape(w) for w in sorted(set(words), key=lambda w: (-len(w), w)))
