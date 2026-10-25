"""The one settings module (Architecture section 12). Environment variables with the VERIDOC_ prefix, plus a local
``.env`` that is never committed. Packages receive values as arguments. No secret has a default value."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOOPBACK = ("127.0.0.1", "localhost")


class SettingsError(ValueError):
    """A setting that is refused (for example a host that is not the local machine)."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERIDOC_", env_file=".env", extra="ignore")

    home: Path = Path("veridoc-home")  # the vault and the logs live here
    host: str = "127.0.0.1"
    port: int = 0  # 0: the launcher picks a free port
    tier: str | None = None  # force a hardware tier
    safe_mode: bool = False
    model_mode: Literal["fake", "local"] = "fake"
    model_dir: Path | None = None
    manifest_path: Path = Path("models/manifest.json")
    max_import_mb: int = 20  # Q-24 placeholder: a setting, not a constant
    log_level: str = "INFO"
    demo_mode: bool = False
    tier_high_min_ram_gb: float = 16
    tier_default_min_ram_gb: float = 8
    tier_low_min_ram_gb: float = 4
    feature_flags: Annotated[list[str], NoDecode] = []
    anchor_enabled: bool = False
    anchor_rpc: str | None = None
    share_base_url: str | None = None
    kdf_test_params: bool = False  # small Argon2id values; refused outside pytest

    @field_validator("host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        if value not in LOOPBACK:
            raise SettingsError("VeriDoc only listens on this computer: use 127.0.0.1 or localhost")
        return value

    @field_validator("feature_flags", mode="before")
    @classmethod
    def _flags(cls, value: object) -> object:
        if isinstance(value, str):
            return [name.strip() for name in value.split(",") if name.strip()]
        return value

    @field_validator("kdf_test_params")
    @classmethod
    def _only_under_pytest(cls, value: bool) -> bool:
        if value and "PYTEST_CURRENT_TEST" not in os.environ:
            raise SettingsError("VERIDOC_KDF_TEST_PARAMS is for tests only")
        return value

    @property
    def max_import_bytes(self) -> int:
        return self.max_import_mb * 1024 * 1024
