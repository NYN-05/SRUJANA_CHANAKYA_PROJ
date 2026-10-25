"""Shared pytest configuration for the VeriDoc phase gate suite.

See PHASES.md section 5. In gate mode (``--gate``) any skipped, xfailed or
xpassed test fails the run, so a phase can never pass by skipping tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
CHATS = FIXTURES / "chats"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

MARKERS = {
    "e2e": "end-to-end through the local API (gate from Phase 9)",
    "perf": "timing budgets (Phase 10 gate only)",
    "model": "needs a real model file in VERIDOC_MODEL_PATH (Phase 10 gate only)",
    "browser": "needs Playwright and a browser (Phase 10 gate only)",
    "node": "needs Node 20 or later",
    "deferred": "Phase 11 specs; never part of the MVP gate",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--gate",
        action="store_true",
        default=False,
        help="Phase gate mode: skipped, xfailed or xpassed tests fail the run.",
    )


def pytest_configure(config: pytest.Config) -> None:
    for name, text in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {text}")


_gate_violations: list[str] = []


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.skipped:
        kind = "xfail" if hasattr(report, "wasxfail") else "skipped"
        _gate_violations.append(f"{kind}: {report.nodeid}")
    elif report.passed and hasattr(report, "wasxfail"):
        _gate_violations.append(f"xpassed: {report.nodeid}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not session.config.getoption("--gate"):
        return
    if _gate_violations:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_sep("=", "GATE FAILED: skipped or xfail tests are not allowed")
            for line in _gate_violations:
                reporter.write_line(line)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    elif session.testscollected == 0:
        session.exitstatus = pytest.ExitCode.NO_TESTS_COLLECTED


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def chats_dir() -> Path:
    return CHATS


@pytest.fixture
def chat_bytes():
    def _load(name: str) -> bytes:
        return (CHATS / name).read_bytes()

    return _load


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def playbooks_dir() -> Path:
    return ROOT / "playbooks"


@pytest.fixture
def supply_playbook(playbooks_dir):
    from packages.intelligence.playbooks import load_playbook

    return load_playbook(playbooks_dir / "supply_order.yaml")


@pytest.fixture
def freelance_playbook(playbooks_dir):
    from packages.intelligence.playbooks import load_playbook

    return load_playbook(playbooks_dir / "freelance.yaml")


@pytest.fixture
def fast_kdf():
    """Small Argon2id parameters so vault tests run fast (real values: Q-23)."""
    from packages.vault import KdfParams

    return KdfParams(time_cost=1, memory_kib=8192, parallelism=1)


@pytest.fixture
def vault(tmp_path, fast_kdf):
    from packages.vault import Vault

    v, _recovery = Vault.create(tmp_path / "vault", "correct horse battery staple", kdf=fast_kdf)
    yield v
    v.lock()


@pytest.fixture
def block_network(monkeypatch):
    """Refuse every socket connection that is not to the loopback interface."""
    import socket

    real_connect = socket.socket.connect

    def guarded(self, address):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise OSError(f"network blocked in test: {host}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield
