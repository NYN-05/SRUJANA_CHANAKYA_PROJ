"""Prompt-injection patterns shared by the rules engine and the model path (I-23, AI_SPEC section 6).

A message that matches is never a term source, for the rules engine or for the model. Chat text is data.
"""

from __future__ import annotations

import re

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(?:all|any|the|previous|prior|above|earlier)(?:\s+\w+){0,3}\s+instructions?",
        r"disregard\s+(?:all|any|the|previous|prior|above)(?:\s+\w+){0,3}\s+instructions?",
        r"\bsystem\s*:",
        r"\bassistant\s*:",
        r"\byou\s+are\s+now\b",
        r"\bset\s+the\s+[^.\n]{0,40}?\s+to\b",
    )
]


def is_injection(text: str) -> bool:
    return any(p.search(text) for p in INJECTION_PATTERNS)
