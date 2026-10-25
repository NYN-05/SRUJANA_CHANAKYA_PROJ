"""Phase 10: launcher, relative paths, tier detection and a real start (NFR-PERF-001, NFR-PORT-001, NFR-PORT-002, ADR-004)."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "packaging"


@pytest.mark.parametrize("name", ["START.bat", "start.sh", "launch.py"])
def test_launcher_files_exist(name):
    assert (PKG / name).is_file()


@pytest.mark.parametrize("name", ["START.bat", "start.sh", "launch.py"])
def test_launcher_uses_relative_paths_only(name):
    text = (PKG / name).read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:\\\\|[A-Za-z]:\\|/home/|/Users/|/opt/", text), f"absolute path in {name}"


def test_start_sh_has_shebang_and_lf():
    data = (PKG / "start.sh").read_bytes()
    assert data.startswith(b"#!") and b"\r\n" not in data


def test_packaging_folder_does_not_shadow_the_packaging_library():
    # a packaging/__init__.py at the repo root would hide the PyPI "packaging" module that pip and pytest use
    assert not (PKG / "__init__.py").exists()


def test_hardware_detection_is_plausible(monkeypatch):
    monkeypatch.syspath_prepend(str(PKG))
    from veridoc_tier import detect_hardware  # packaging/veridoc_tier.py

    ram_gb, has_avx2 = detect_hardware()
    assert 0.5 < ram_gb < 4096 and isinstance(has_avx2, bool)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_launch_serves_health_on_loopback_within_15s(tmp_path):
    port = free_port()
    env = dict(os.environ, VERIDOC_HOME=str(tmp_path / "home"), VERIDOC_MODEL_MODE="fake", VERIDOC_PORT=str(port))
    proc = subprocess.Popen([sys.executable, str(PKG / "launch.py"), "--no-browser"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 15  # NFR-PERF-001 target
        body = None
        while time.time() < deadline and body is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
                    body = json.loads(r.read())
            except OSError:
                time.sleep(0.25)
        assert body and body["status"] == "ok", "app not usable within 15 s"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_server_refuses_non_loopback_bind(tmp_path):
    env = dict(os.environ, VERIDOC_HOME=str(tmp_path / "home"), VERIDOC_HOST="0.0.0.0")
    proc = subprocess.run([sys.executable, str(PKG / "launch.py"), "--no-browser"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode != 0
