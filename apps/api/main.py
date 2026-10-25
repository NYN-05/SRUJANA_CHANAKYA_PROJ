"""The local API (Architecture sections 10 to 13). Binds to this computer only; serves the web UI from ``apps/web``.

``create_app`` wires the routers that ``discover_routers`` finds (ADR-022), the origin check (T16), the error shape
and the logging middleware. Nothing is logged except event names, route templates, status codes and durations.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from packages.ingest.commit import SelectionError
from packages.ingest.errors import ImportRefused
from packages.vault import NothingToVersion, TermNotConfirmable, VaultLocked, WrongPassphrase

from .errors import ApiError
from .settings import Settings
from .state import AppContext

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"
VERIFY_PAGE = ROOT / "apps" / "verify" / "verify.html"
log = logging.getLogger("veridoc.api")


class RouterImportError(RuntimeError):
    """A router module failed to import. Startup stops and names the module (ADR-022); it is never skipped silently."""


def discover_routers(package_name: str) -> list[tuple[str, APIRouter]]:
    """Every module in the package that exposes ``router``."""
    package = importlib.import_module(package_name)
    found = []
    for info in pkgutil.iter_modules(package.__path__):
        try:
            module = importlib.import_module(f"{package_name}.{info.name}")
        except Exception as exc:
            raise RouterImportError(f"router module {info.name!r} failed to import ({type(exc).__name__})") from exc
        if isinstance(getattr(module, "router", None), APIRouter):
            found.append((info.name, module.router))
    return found


class WebFiles(StaticFiles):
    """The web UI. A path that is not a file serves the app shell, so /import and /deal/<id> work after a reload."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api") and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise


# typed errors from the packages -> the fixed error codes
MAPPED: list[tuple[type[Exception], str]] = [
    (TermNotConfirmable, "term_not_confirmable"),
    (NothingToVersion, "nothing_to_version"),
    (VaultLocked, "locked"),
    (WrongPassphrase, "wrong_passphrase"),
    (SelectionError, "bad_selection"),
    (ValidationError, "invalid_request"),
    (KeyError, "not_found"),
    (ValueError, "bad_request"),
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    context = AppContext(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        context.close()
        context.stop_logging()

    app = FastAPI(title="VeriDoc", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.ctx = context

    def failure(error: ApiError) -> JSONResponse:
        return JSONResponse(error.body(), status_code=error.status)

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        started = time.perf_counter()
        origin = request.headers.get("origin")
        if origin is not None and origin != f"{request.url.scheme}://{request.headers.get('host', '')}":
            response: Response = failure(ApiError("forbidden_origin"))  # another page tried to talk to the local app (T16)
        else:
            try:
                response = await call_next(request)
            except Exception as exc:
                log.error("internal_error type=%s", type(exc).__name__)
                response = failure(ApiError("internal"))
        template = getattr(request.scope.get("route"), "path", "unmatched")
        log.info("request %s %s status=%d ms=%d", request.method, template, response.status_code, (time.perf_counter() - started) * 1000)
        return response

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return failure(exc)

    @app.exception_handler(ImportRefused)
    async def _refused(_request: Request, exc: ImportRefused) -> JSONResponse:
        return failure(ApiError("too_large" if exc.code in ("too_large", "zip_limits") else "unreadable_file"))

    @app.exception_handler(RequestValidationError)
    async def _invalid(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return failure(ApiError("invalid_request"))  # the body never echoes what was sent

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return failure(ApiError("not_found" if exc.status_code == 404 else "bad_request"))

    for kind, code in MAPPED:
        app.add_exception_handler(kind, lambda _r, _e, code=code: failure(ApiError(code)))  # type: ignore[misc]

    for _name, router in discover_routers("apps.api.routers"):
        app.include_router(router, prefix="/api")

    if VERIFY_PAGE.is_file():
        app.add_api_route("/verify.html", lambda: FileResponse(VERIFY_PAGE), include_in_schema=False)
    if WEB.is_dir():
        app.mount("/", WebFiles(directory=WEB, html=True), name="web")
    return app
