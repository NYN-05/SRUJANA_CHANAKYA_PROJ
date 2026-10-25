"""Phase 9: no content in logs across the whole flow (AC-9.3, NFR-PRV-002, THREAT_MODEL T17)."""

from __future__ import annotations

import logging

import pytest
from test_e2e_demo_flow import run_demo

pytestmark = pytest.mark.e2e

FORBIDDEN = [
    "200 shirts",
    "480 each",
    "next week",
    "done sent 48000",
    "haan theek hai",
    "Raju",
    "Meena",
    "correct horse battery staple",
    "₹48,000",
    "CONFIRM ",
]


def test_logs_hold_no_content(api, caplog):
    caplog.set_level(logging.DEBUG)
    run_demo(api)
    assert caplog.records
    for needle in FORBIDDEN:
        assert needle not in caplog.text, f"log line contains {needle!r}"


def test_log_files_on_disk_hold_no_content(api, app_settings):
    run_demo(api)
    logs = list((app_settings.home / "logs").rglob("*")) if (app_settings.home / "logs").exists() else []
    text = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in logs if p.is_file())
    for needle in FORBIDDEN:
        assert needle not in text
