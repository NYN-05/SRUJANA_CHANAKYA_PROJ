"""Phase 0 (re-checked in every later gate): static dependency rules.

Architecture section 3 dependency rules 1, 2 and 5; FR-AIS-001; ADR-007.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "packages"

NETWORK_MODULES = {"socket", "http", "urllib", "requests", "httpx", "aiohttp", "websocket", "websockets", "ftplib", "smtplib"}
NETWORK_ALLOWED = ("packages/integrity/anchoring/", "packages/vault/share/")
HASH_MODULES = {"packages.integrity.hashing", "packages.integrity.merkle", "packages.integrity.chain", "packages.integrity.echo"}


def _py_files(base: Path):
    return [p for p in base.rglob("*.py") if "tests" not in p.parts and "migrations" not in p.parts]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def test_packages_folder_exists():
    assert PACKAGES.is_dir()


def test_intelligence_never_imports_vault_or_hash_path():
    offenders = []
    for path in _py_files(PACKAGES / "intelligence"):
        for name in _imports(path):
            if name == "packages.vault" or name.startswith("packages.vault."):
                offenders.append((_rel(path), name))
            if name == "packages.integrity" or any(name == m or name.startswith(m + ".") for m in HASH_MODULES):
                offenders.append((_rel(path), name))
    assert offenders == [], f"AI package must not reach the vault or hash path: {offenders}"


@pytest.mark.parametrize("pkg", ["contracts", "ingest", "intelligence", "integrity", "vault"])
def test_cross_package_imports_only_contracts(pkg):
    allowed = {"contracts", pkg}
    if pkg == "vault":
        allowed.add("integrity")  # the vault calls the integrity engine (Architecture section 3)
    if pkg == "contracts":
        allowed = {"contracts"}
    offenders = []
    for path in _py_files(PACKAGES / pkg):
        for name in _imports(path):
            if name.startswith("packages."):
                other = name.split(".")[1]
                if other not in allowed:
                    offenders.append((_rel(path), name))
    assert offenders == [], f"packages/{pkg} imports another package: {offenders}"


def test_network_libraries_only_in_allowed_modules():
    offenders = []
    for base in (PACKAGES, ROOT / "apps"):
        for path in _py_files(base):
            rel = _rel(path)
            if rel.startswith(NETWORK_ALLOWED):
                continue
            for name in _imports(path):
                if name.split(".")[0] in NETWORK_MODULES:
                    offenders.append((rel, name))
    # the API server itself is started by uvicorn; it imports no client network library
    assert offenders == [], f"network libraries outside anchoring and share modules: {offenders}"


def test_contracts_has_no_io():
    for path in _py_files(PACKAGES / "contracts"):
        names = _imports(path)
        assert not (names & {"sqlite3", "sqlalchemy", "subprocess"}), _rel(path)
        assert "open(" not in path.read_text(encoding="utf-8"), f"{_rel(path)} must not do file I/O"
