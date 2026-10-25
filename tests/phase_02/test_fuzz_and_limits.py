"""Phase 2: robustness. Fuzz input, long messages, linear time (THREAT_MODEL T14, AC-2.7)."""

from __future__ import annotations

import random
import time

from packages.ingest.errors import ImportRefused
from packages.ingest.whatsapp import parse_export

PIECES = [
    "14/10/26, 09:00 - Raju: ",
    "[14/10/2026, 09:00:00] Meena: ",
    "14/10/26, 9:00 pm - ",
    "‎",
    " ",
    "<Media omitted>",
    ": ",
    " - ",
    "[",
    "]",
    "/",
    ",",
    "\n",
    "\r\n",
    "ठीक",
    "ಸರಿ",
    "👍",
    "1.5 lakh",
    "99/99/99, 99:99 - X: ",
    "a" * 50,
]


def test_fuzz_never_raises_unexpected_errors():
    rng = random.Random(20261025)
    for _ in range(2000):
        doc = "".join(rng.choice(PIECES) for _ in range(rng.randint(0, 40)))
        try:
            r = parse_export(doc.encode("utf-8"))
        except ImportRefused:
            continue
        seqs = [m.seq for m in r.messages]
        assert seqs == list(range(1, len(seqs) + 1))


def test_hundred_kb_message_parses_quickly():
    body = "x" * 100_000
    data = f"14/10/26, 09:00 - Raju: {body}\n14/10/26, 09:01 - Meena: ok\n".encode()
    start = time.perf_counter()
    r = parse_export(data)
    assert time.perf_counter() - start < 1.0
    assert len(r.messages[0].text) == 100_000


def test_parse_time_grows_linearly():
    def timed(n: int) -> float:
        lines = "".join(f"14/10/26, 09:{i % 60:02d} - Raju: message number {i} with 480 each\n" for i in range(n))
        start = time.perf_counter()
        parse_export(lines.encode())
        return time.perf_counter() - start

    small, large = timed(2000), timed(20000)
    assert large < small * 30, f"parsing is not linear: {small:.3f}s vs {large:.3f}s"


def test_pathological_header_like_line_no_backtracking():
    evil = "14/10/26, 09:00 - " + "Raju: " * 5000 + "\n"
    start = time.perf_counter()
    parse_export(evil.encode())
    assert time.perf_counter() - start < 1.0
