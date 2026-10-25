"""Phase 1: run the Node vector tests from pytest so the gate covers both languages."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.node
def test_node_is_available():
    node = shutil.which("node")
    assert node, "Node 20 or later is required (DOCS/TEAM.md › Developer Setup)"
    major = int(subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")[0])
    assert major >= 20


@pytest.mark.node
def test_js_integrity_reproduces_vectors():
    node = shutil.which("node")
    assert node, "Node is required"
    out = subprocess.run(
        [node, "--test", "tests/phase_01/js/*.test.mjs"],  # Node expands the glob itself
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stdout[-4000:] + out.stderr[-2000:]
