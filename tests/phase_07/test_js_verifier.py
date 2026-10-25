"""Phase 7: the JavaScript verifier gives the same verdicts as the Python verifier (THREAT_MODEL T20)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from bundle_builder import build_bundle
from test_tamper_cases import CASES

from packages.integrity.verify import verify_bundle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def js_verify(path: Path) -> dict:
    node = shutil.which("node")
    assert node, "Node 20 or later is required"
    out = subprocess.run([node, str(HERE / "js" / "verify_cli.mjs"), str(path)], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def summary(py):
    fd = py.first_difference
    return {"verdict": py.verdict, "kind": fd.kind if fd else None, "seq": fd.seq if fd else None, "version_n": fd.version_n if fd else None}


@pytest.mark.node
def test_untampered(tmp_path):
    p = tmp_path / "ok.zip"
    p.write_bytes(build_bundle().zip_bytes())
    assert js_verify(p) == summary(verify_bundle(p))


@pytest.mark.node
@pytest.mark.parametrize("name,tamper,expected", CASES, ids=[c[0] for c in CASES])
def test_tamper_cases_match_python(tmp_path, name, tamper, expected):
    p = tmp_path / f"{name}.zip"
    p.write_bytes(tamper(build_bundle()).zip_bytes())
    assert js_verify(p) == summary(verify_bundle(p))


@pytest.mark.node
def test_node_suite_on_generated_fixtures():
    node = shutil.which("node")
    assert node
    out = subprocess.run([node, "--test", "tests/phase_07/js/*.test.mjs"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout[-4000:] + out.stderr[-2000:]
