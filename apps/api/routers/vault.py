"""The vault: setup, unlock, lock and the deal list (Architecture section 10)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from packages.vault import DEFAULT_KDF, Vault, WrongPassphrase

from ..errors import ApiError
from ..pipeline import deal_of
from ..state import AppContext, current_vault, get_ctx

router = APIRouter()


class Setup(BaseModel):
    passphrase: str = Field(min_length=1)


class Unlock(BaseModel):
    passphrase: str | None = None
    recovery_key: str | None = None


def _exists(ctx: AppContext) -> bool:
    return (ctx.settings.home / "vault.json").is_file()


@router.get("/vault/status")
def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, bool]:
    return {"exists": _exists(ctx), "unlocked": ctx.vault is not None}


@router.post("/vault/setup")
def setup(body: Setup, ctx: AppContext = Depends(get_ctx)) -> dict[str, str]:
    """Create the vault. The recovery key is shown once and never stored."""
    if _exists(ctx):
        raise ApiError("setup_exists")
    vault, recovery_key = Vault.create(ctx.settings.home, body.passphrase, kdf=ctx.kdf or DEFAULT_KDF)
    vault.lock()
    return {"recovery_key": recovery_key}


@router.post("/vault/unlock")
def unlock(body: Unlock, ctx: AppContext = Depends(get_ctx)) -> dict[str, str]:
    if body.passphrase is None and body.recovery_key is None:
        raise ApiError("invalid_request")
    if not _exists(ctx):
        raise ApiError("no_vault")
    try:
        vault = Vault.unlock(ctx.settings.home, passphrase=body.passphrase, recovery_key=body.recovery_key)
    except WrongPassphrase as exc:
        raise ApiError("wrong_passphrase") from exc
    return {"token": ctx.open(vault)}


@router.post("/vault/lock")
def lock(ctx: AppContext = Depends(get_ctx), _vault: Vault = Depends(current_vault)) -> dict[str, bool]:
    ctx.close()
    return {"locked": True}


@router.get("/deals")
def deals(vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return {"deals": [
        {"id": d.id, "playbook_key": d.playbook_key, "created_at": d.created_at, "me": d.me_id, "counterparty": d.counterparty_id}
        for d in vault.deals()
    ]}


@router.get("/deals/{deal_id}")
def deal(deal_id: str, vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    d = deal_of(vault, deal_id)
    return {"id": d.id, "playbook_key": d.playbook_key, "created_at": d.created_at, "me": d.me_id, "counterparty": d.counterparty_id,
            "date_order": d.date_order, "participants": [p.__dict__ for p in vault.participants(deal_id)]}


@router.get("/deals/{deal_id}/messages")
def messages(deal_id: str, vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    deal_of(vault, deal_id)
    return {"messages": [m.model_dump(mode="json") for m in vault.messages(deal_id)]}
