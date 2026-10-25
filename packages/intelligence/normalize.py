"""Text normalisation for the rules engine (AI_SPEC section 2, step 1).

NFC, Devanagari / Kannada / full-width digits to ASCII, whitespace collapsed. The original text is never
changed: a ``Normalized`` keeps, for every normalised character, the span of original characters it came
from, so parsers can report spans in the text the user sees (S4 highlights the exact words).
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from dataclasses import dataclass

_DIGITS = {ord(c): str(i) for i in range(10) for c in (chr(0x966 + i), chr(0xCE6 + i), chr(0xFF10 + i))}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


@dataclass(frozen=True)
class Normalized:
    original: str
    text: str
    starts: tuple[int, ...]  # original start of the source of each normalised character
    ends: tuple[int, ...]  # original end (exclusive)

    def locate(self, start: int, end: int) -> dict[str, object]:
        """Original-text span for the normalised range [start, end), as keyword arguments for a match."""
        s, e = self.starts[start], self.ends[end - 1]
        return {"start": s, "end": e, "raw": self.original[s:e]}

    def norm_index(self, original_index: int) -> int:
        """Index in the normalised text of the character that covers an original index."""
        return max(0, min(bisect_right(self.starts, original_index) - 1, len(self.text) - 1))


def normalize(text: str) -> Normalized:
    out: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    pending: tuple[int, int] | None = None
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            if out:
                pending = (i, j)
            i = j
            continue
        j = i + 1
        while j < n and unicodedata.category(text[j]).startswith("M"):
            j += 1
        if pending:
            out.append(" ")
            starts.append(pending[0])
            ends.append(pending[1])
            pending = None
        for ch in nfc(text[i:j]).translate(_DIGITS):
            out.append(ch)
            starts.append(i)
            ends.append(j)
        i = j
    return Normalized(text, "".join(out), tuple(starts), tuple(ends))


def normalize_for_rules(text: str) -> str:
    return normalize(text).text
