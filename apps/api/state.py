"""Process state shared by the routers: settings, the open vault, the session token, import previews, the model.

Dependencies (``current_vault``) are what routers use to require a session; the token is compared in constant time.
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import Request

from packages.intelligence.model.fake import FakeModelRunner
from packages.intelligence.model.models import ModelStatus, verify_model_file
from packages.intelligence.playbooks import Playbook, load_all
from packages.vault import KdfParams, Vault

from .errors import ApiError
from .settings import Settings

TOKEN_HEADER = "X-VeriDoc-Session"
PLAYBOOKS_DIR = Path(__file__).resolve().parents[2] / "playbooks"
TEST_KDF = KdfParams(time_cost=1, memory_kib=8192, parallelism=1)  # tests only (Q-23)
MAX_PREVIEWS = 20
log = logging.getLogger("veridoc.api")


@dataclass
class Preview:
    """An import the person has looked at but not accepted. Nothing is stored until commit."""

    chat: bytes | str  # what the parser reads: file bytes, or pasted text
    raw: bytes  # the file as given: its SHA-256 is the export digest
    file_name: str
    origin: str  # export | paste
    media: dict[str, bytes] = field(default_factory=dict)


class AppContext:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vault: Vault | None = None
        self.token: str | None = None
        self.safe_mode = settings.safe_mode  # read on every analysis call, so a toggle needs no restart
        self.previews: dict[str, Preview] = {}
        self._playbooks: dict[str, Playbook] | None = None
        self._model: tuple[ModelStatus, Any] | None = None
        self._handler: RotatingFileHandler | None = None

    @property
    def playbooks(self) -> dict[str, Playbook]:
        if self._playbooks is None:
            self._playbooks = load_all(PLAYBOOKS_DIR)
        return self._playbooks

    @property
    def kdf(self) -> KdfParams | None:
        return TEST_KDF if self.settings.kdf_test_params else None

    def add_preview(self, preview: Preview) -> str:
        if len(self.previews) >= MAX_PREVIEWS:
            self.previews.pop(next(iter(self.previews)))
        preview_id = str(uuid.uuid4())
        self.previews[preview_id] = preview
        return preview_id

    def open(self, vault: Vault) -> str:
        self.close()
        self.vault, self.token = vault, secrets.token_urlsafe(32)
        self._start_file_log()
        return self.token

    def close(self) -> None:
        if self.vault is not None:
            self.vault.lock()
        self.vault = self.token = None
        self.previews.clear()

    def _start_file_log(self) -> None:
        """Logs stay in VERIDOC_HOME, rotate at a small size and carry event names and counts only."""
        if self._handler is not None:
            return
        logs = self.settings.home / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self._handler = RotatingFileHandler(logs / "veridoc.log", maxBytes=256 * 1024, backupCount=2, encoding="utf-8")
        self._handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger("veridoc").setLevel(self.settings.log_level.upper())
        logging.getLogger("veridoc").addHandler(self._handler)

    def stop_logging(self) -> None:
        if self._handler is not None:
            logging.getLogger("veridoc").removeHandler(self._handler)
            self._handler.close()
            self._handler = None

    def model(self) -> tuple[ModelStatus, Any]:
        """(status, runner). ``fake`` mode uses recorded output; ``local`` loads the manifest's extraction model once."""
        if self._model is None:
            tier = self.settings.tier or "default"
            if self.settings.model_mode == "fake":
                self._model = (ModelStatus(True, True, 0, tier), FakeModelRunner('{"terms": []}'))
            else:
                self._model = self._load_local(tier)
        return self._model

    def _load_local(self, tier: str) -> tuple[ModelStatus, Any]:
        try:
            manifest = json.loads(self.settings.manifest_path.read_text(encoding="utf-8"))
            entry = next(e for e in manifest["models"] if e["role"] == "extraction" and e["tier"] == tier)
            path = (self.settings.model_dir or Path(".")) / entry["file"]
        except (OSError, ValueError, KeyError, StopIteration):
            return ModelStatus(False, None, 0, tier), None
        if not path.is_file():
            return ModelStatus(False, None, 0, tier), None
        if not verify_model_file(path, entry):
            return ModelStatus(True, False, 0, tier), None
        try:
            from packages.intelligence.model.llama_cpp import LlamaCppRunner

            return ModelStatus(True, True, 0, tier), LlamaCppRunner(path)
        except Exception:
            log.warning("model_load_failed")
            return ModelStatus(True, True, 2, tier), None


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx  # type: ignore[no-any-return]


def current_vault(request: Request) -> Vault:
    """The open vault, or 401. The token must match in constant time."""
    ctx = get_ctx(request)
    sent = request.headers.get(TOKEN_HEADER, "")
    if ctx.vault is None or ctx.token is None or not secrets.compare_digest(sent.encode(), ctx.token.encode()):
        raise ApiError("locked")
    return ctx.vault
