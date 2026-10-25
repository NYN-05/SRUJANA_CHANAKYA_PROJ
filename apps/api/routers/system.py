"""Health and settings (Architecture section 10). Health needs no token and reveals no content."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from packages.contracts import CONTRACT_VERSION
from packages.integrity.receipt import SPEC_VERSION
from packages.vault import Vault

from ..pipeline import mode_of
from ..state import AppContext, current_vault, get_ctx

router = APIRouter()
log = logging.getLogger("veridoc.api")


class SettingsBody(BaseModel):
    safe_mode: bool


@router.get("/health")
def health(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {
        "status": "ok",
        "safe_mode": ctx.safe_mode,
        "tier": ctx.settings.tier or "default",
        "spec_version": SPEC_VERSION,
        "contract_version": CONTRACT_VERSION,
    }


def _view(ctx: AppContext) -> dict[str, Any]:
    mode, reason = mode_of(ctx)
    return {
        "safe_mode": ctx.safe_mode,
        "analysis_mode": mode,
        "analysis_reason": reason,
        "model_mode": ctx.settings.model_mode,
        "tier": ctx.settings.tier or "default",
        "feature_flags": list(ctx.settings.feature_flags),
        "max_import_mb": ctx.settings.max_import_mb,
        "offline": True,
    }


@router.get("/settings")
def get_settings(ctx: AppContext = Depends(get_ctx), _vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return _view(ctx)


@router.post("/settings")
def change_settings(body: SettingsBody, ctx: AppContext = Depends(get_ctx), _vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """The kill switch (FR-AIS-005): read on every analysis call, so it takes effect without a restart."""
    ctx.safe_mode = body.safe_mode
    log.info("safe_mode_on" if body.safe_mode else "safe_mode_off")
    return _view(ctx)
