"""Phase 0: app factory, health route and router auto-discovery (ADR-022)."""

from __future__ import annotations

import sys
import textwrap

import pytest


def test_health_route_returns_required_keys():
    from fastapi.testclient import TestClient

    from apps.api.main import create_app

    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("status", "safe_mode", "tier", "spec_version", "contract_version"):
        assert key in body, f"health is missing {key}"
    assert body["status"] == "ok"


def _make_router_package(tmp_path, name, modules):
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for mod, src in modules.items():
        (pkg / f"{mod}.py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.modules.pop(name, None)
    return name


GOOD = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/ping")
def ping():
    return {"pong": True}
"""

BROKEN = """
raise RuntimeError("boom at import")
"""

NO_ROUTER = """
VALUE = 1
"""


def test_discover_routers_finds_each_module(tmp_path, monkeypatch):
    from apps.api.main import discover_routers

    monkeypatch.syspath_prepend(str(tmp_path))
    name = _make_router_package(tmp_path, "routers_ok", {"alpha": GOOD, "beta": GOOD})
    found = dict(discover_routers(name))
    assert set(found) == {"alpha", "beta"}


def test_module_without_router_is_ignored(tmp_path, monkeypatch):
    from apps.api.main import discover_routers

    monkeypatch.syspath_prepend(str(tmp_path))
    name = _make_router_package(tmp_path, "routers_mixed", {"alpha": GOOD, "helpers": NO_ROUTER})
    assert [n for n, _ in discover_routers(name)] == ["alpha"]


def test_broken_router_is_reported_by_name(tmp_path, monkeypatch):
    from apps.api.main import RouterImportError, discover_routers

    monkeypatch.syspath_prepend(str(tmp_path))
    name = _make_router_package(tmp_path, "routers_bad", {"alpha": GOOD, "broken": BROKEN})
    with pytest.raises(RouterImportError) as err:
        discover_routers(name)
    assert "broken" in str(err.value)


def test_real_routers_package_imports_cleanly():
    from apps.api.main import discover_routers

    discover_routers("apps.api.routers")  # must not raise


def test_unknown_route_is_404_without_traceback():
    from fastapi.testclient import TestClient

    from apps.api.main import create_app

    resp = TestClient(create_app()).get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text
