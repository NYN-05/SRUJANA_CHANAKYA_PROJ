"""Live analysis, term actions, the score and the suggested message (S3, S4; FR-SCO-003, FR-SUG-001 to 004, FR-AIS-005)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from packages.contracts import Tone
from packages.vault import Vault

from ..pipeline import (
    Snapshot,
    mode_of,
    record,
    refined,
    rules_result,
    score_now,
    score_payload,
    snapshot,
    suggest,
    term_payload,
)
from ..state import AppContext, current_vault, get_ctx

router = APIRouter()


class ValueBody(BaseModel):
    value: dict[str, Any] | None = None


class CorrectBody(BaseModel):
    value: dict[str, Any]


class CopiedBody(BaseModel):
    text: str | None = None  # accepted so the screen can send it; it is never stored


def _suggestion(snap: Snapshot) -> dict[str, Any]:
    """The suggested message in all three tones, so the screen can switch without another call."""
    texts, first = {}, None
    for tone in Tone:
        s = suggest(snap, tone, "en")
        if s is not None:
            texts[tone.value], first = s.text, first or s
    return {
        "target_term_keys": first.target_term_keys if first else [],
        "needs_user_input": first.needs_user_input if first else [],
        "texts": texts,
    }


def _events(snap: Snapshot, terms_event: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (terms_event, {"terms": [term_payload(t, snap.agreed, snap.playbook) for t in snap.terms]}),
        ("flags", {"flags": [f.model_dump(mode="json") for f in snap.flags]}),
        ("score", score_payload(snap.score)),
        ("suggestion", _suggestion(snap)),
    ]


def _sse(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/deals/{deal_id}/analysis/stream")
async def stream(deal_id: str, request: Request, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> StreamingResponse:
    """Server-sent events in this order: terms, flags, score, suggestion (rules), then the same four if the model ran
    (``terms_refined`` first), then done. The model never delays the rules result."""
    deal, playbook, messages, rules = await asyncio.to_thread(rules_result, vault, ctx, deal_id)

    async def events() -> AsyncIterator[str]:
        first = await asyncio.to_thread(snapshot, ctx, vault, deal_id, rules)
        for name, data in _events(first, "terms"):
            if await request.is_disconnected():
                return
            yield _sse(name, data)
        mode, reason = mode_of(ctx)
        result = await asyncio.to_thread(refined, ctx, deal, playbook, messages, rules)
        final = rules
        error = None
        if result is not None:
            error, final = result.error, result.terms
            if result.used_model:
                for name, data in _events(await asyncio.to_thread(snapshot, ctx, vault, deal_id, final), "terms_refined"):
                    if await request.is_disconnected():
                        return
                    yield _sse(name, data)
        await asyncio.to_thread(vault.save_proposals, deal_id, final)
        yield _sse("done", {"mode": mode, "reason": reason, "error": error})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@router.get("/deals/{deal_id}/workspace")
def workspace(deal_id: str, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """Terms, flags, score and suggestion as stored, for a screen that opens a deal."""
    snap = snapshot(ctx, vault, deal_id)
    return {name: data for name, data in _events(snap, "terms")} | {"messages": [m.model_dump(mode="json") for m in snap.messages]}


@router.get("/deals/{deal_id}/score")
def score(deal_id: str, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return score_payload(snapshot(ctx, vault, deal_id).score)


def _act(ctx: AppContext, vault: Vault, deal_id: str, trigger: str, action: Any) -> dict[str, Any]:
    before = score_now(ctx, vault, deal_id)
    result = action()
    after = record(ctx, vault, deal_id, trigger).score.score
    return {**result, "score_before": before, "score_after": after}


@router.post("/deals/{deal_id}/terms/{key}/confirm")
def confirm(deal_id: str, key: str, body: ValueBody | None = None, ctx: AppContext = Depends(get_ctx),
            vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """Confirm a clear proposal as it is, or confirm a value the person typed (needed for unclear, conflict, missing)."""
    value = body.value if body else None
    return _act(ctx, vault, deal_id, "term_confirmed", lambda: {"term": vault.confirm_term(deal_id, key, value).model_dump(mode="json")})


@router.post("/deals/{deal_id}/terms/{key}/correct")
def correct(deal_id: str, key: str, body: CorrectBody, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return _act(ctx, vault, deal_id, "term_corrected", lambda: {"term": vault.correct_term(deal_id, key, body.value).model_dump(mode="json")})


@router.post("/deals/{deal_id}/terms/{key}/reject")
def reject(deal_id: str, key: str, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return _act(ctx, vault, deal_id, "term_rejected", lambda: (vault.reject_term(deal_id, key), {"rejected": True})[1])


@router.get("/deals/{deal_id}/suggestion")
def suggestion(deal_id: str, tone: Tone = Tone.POLITE, language: Literal["en", "hi"] = "en", ctx: AppContext = Depends(get_ctx),
               vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """One suggested next message. The person copies it and sends it in WhatsApp; nothing here sends (FR-SUG-003)."""
    s = suggest(snapshot(ctx, vault, deal_id), tone, language)
    if s is None:
        return {"target_term_keys": [], "tone": tone.value, "language": language, "text": "", "needs_user_input": []}
    return s.model_dump(mode="json")


@router.post("/deals/{deal_id}/suggestion/copied")
def suggestion_copied(deal_id: str, body: CopiedBody | None = None, vault: Vault = Depends(current_vault)) -> dict[str, bool]:
    vault.record_event(deal_id, "suggestion_copied")
    return {"copied": True, "sent": False}
