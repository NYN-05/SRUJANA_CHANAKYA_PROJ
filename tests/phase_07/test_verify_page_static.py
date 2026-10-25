"""Phase 7: verify.html is one offline file with the required copy (FR-VFY-001, FR-VFY-006, ADR-015, S9)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "apps" / "verify" / "verify.html"
LIMIT = "This checks that the record was not changed after it was saved. It cannot prove that the original chat export was genuine."


@pytest.fixture(scope="module")
def html():
    assert PAGE.is_file(), "apps/verify/verify.html is required"
    return PAGE.read_text(encoding="utf-8")


@pytest.mark.parametrize("banned", ["http://", "https://", "fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "navigator.sendBeacon", "<link", "@import", "import(", "<iframe"])
def test_no_network_or_external_resources(html, banned):
    assert banned not in html, f"verify.html must not contain {banned}"


def test_no_external_src_attributes(html):
    for src in re.findall(r"""src\s*=\s*["']([^"']+)["']""", html):
        assert src.startswith("data:"), f"external src: {src}"


def test_limit_text_always_present(html):
    assert LIMIT in html


@pytest.mark.parametrize("copy", ["No login", "no network", "nothing is uploaded", "UNCHANGED since recording", "ALTERED after recording", "This file is not a VeriDoc receipt bundle."])
def test_required_copy(html, copy):
    assert copy in html


def test_status_symbols_paired_with_words(html):
    assert "✓ UNCHANGED" in html and "⚠ ALTERED" in html


def test_page_is_built_from_the_tested_modules():
    # scripts/build_verify_page.py inlines integrity.mjs and verify.mjs; --check fails if the page is stale
    script = ROOT / "scripts" / "build_verify_page.py"
    assert script.is_file()
    out = subprocess.run([sys.executable, str(script), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_results_are_written_with_text_nodes_not_html(html):
    assert "innerHTML" not in html and "document.write" not in html and "eval(" not in html


def test_page_has_a_drop_zone_and_a_file_picker(html):
    assert 'type="file"' in html and "dragover" in html


def test_page_includes_the_verifier_and_the_primitives(html):
    assert "async function verifyBundle" in html and "async function merkleRoot" in html
    assert "export " not in html.split("<script>")[1], "modules are inlined as plain script"


def test_page_is_small_enough_to_audit():
    assert PAGE.stat().st_size < 300_000
