"""Phase 10: timing budgets (NFR-PERF-003; PERFORMANCE section 2 extra rows). Targets until measured."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pytest
from helpers import chat_of, make_messages

from packages.contracts import MessageOrigin
from packages.ingest.commit import prepare_commit
from packages.ingest.whatsapp import parse_export
from packages.intelligence.extract import extract_terms

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase_07"))
from bundle_builder import build_bundle  # noqa: E402

from packages.integrity.verify import verify_bundle  # noqa: E402

pytestmark = pytest.mark.perf


def p95(values):
    return statistics.quantiles(values, n=20)[-1]


def test_rules_p95_per_message_under_100ms(supply_playbook):
    texts = ["200 shirts, 480 each ok?", "ok. delivery next week", "advance half now", "done sent 48000", "balance 40,000 on delivery", "approx 50k", "late fee 500 per day", "baaki 30 din baad"]
    timings = []
    for i in range(1000):
        msgs = make_messages([("Raju" if i % 2 else "Meena", texts[i % len(texts)])])
        start = time.perf_counter()
        extract_terms(msgs, supply_playbook, me_id="Raju", counterparty_id="Meena", date_order="DMY")
        timings.append(time.perf_counter() - start)
    assert p95(timings) < 0.1, f"p95 {p95(timings):.4f}s"


def test_150_message_import_to_first_rules_result_under_2s(supply_playbook):
    raw = chat_of(150)
    start = time.perf_counter()
    d = prepare_commit(parse_export(raw), me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)
    extract_terms(d.messages, supply_playbook, me_id=d.me_id, counterparty_id=d.counterparty_id, date_order="DMY")
    assert time.perf_counter() - start < 2.0


def test_vault_write_of_150_messages_under_1s(vault):
    raw = chat_of(150)
    d = prepare_commit(parse_export(raw), me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)
    start = time.perf_counter()
    vault.commit_import(d, export_bytes=raw, file_name="c.txt", media={})
    assert time.perf_counter() - start < 1.0


def test_python_verify_of_1000_leaves_under_2s():
    data = build_bundle(n_messages=990, versions=3).zip_bytes()
    start = time.perf_counter()
    assert verify_bundle(data).verdict == "UNCHANGED"
    assert time.perf_counter() - start < 2.0
