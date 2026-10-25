"""Import: samples, preview, commit and the simulator (FR-IMP-001 to 009, S2). Nothing is stored until commit."""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from packages.contracts import MessageOrigin
from packages.ingest.archive import read_export_zip
from packages.ingest.commit import SelectionError, prepare_commit
from packages.ingest.preview import ImportPreview, build_preview
from packages.ingest.samples import list_samples, load_sample
from packages.ingest.whatsapp import parse_export
from packages.vault import Vault

from ..errors import ApiError
from ..pipeline import deal_of, reanalyse, record, score_now
from ..state import AppContext, Preview, current_vault, get_ctx

router = APIRouter()
PRIVACY_LINE = "This chat stays on this device. Nothing is uploaded."
DATE_ORDERS = (None, "DMY", "MDY")


class Commit(BaseModel):
    preview_id: str
    me: str
    counterparty: str
    playbook_key: str
    date_order: Literal["DMY", "MDY"] | None = None
    deal_id: str | None = None  # add this chat to an existing deal instead of making a new one


class Simulated(BaseModel):
    sender: str
    text: str = Field(min_length=1, max_length=5000)


def _payload(preview_id: str, p: ImportPreview) -> dict[str, Any]:
    first, last = p.date_range
    return {
        "preview_id": preview_id,
        "file_name": p.file_name,
        "message_count": p.message_count,
        "media_count": p.media_count,
        "participants": p.participants,
        "date_range": [first.isoformat(), last.isoformat()] if first and last else None,
        "date_order": p.date_order,
        "needs_date_order_choice": p.needs_date_order_choice,
        "format_problem": p.format_problem,
        "first_unparsed_lines": [[n, line] for n, line in p.first_unparsed_lines],
        "warnings": p.warnings,
        "export_digest": p.export_digest,
        "privacy_line": PRIVACY_LINE,
    }


@router.get("/ingest/samples")
def samples(_vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return {"samples": [{"name": name} for name in list_samples()]}


@router.post("/ingest/preview")
async def preview(request: Request, ctx: AppContext = Depends(get_ctx), _vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """A file (multipart ``file``), pasted text (``{"text"}``) or a sample (``{"sample"}``); ``date_order`` is optional."""
    origin, date_order = "export", None
    if request.headers.get("content-type", "").startswith("multipart/"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or isinstance(upload, str):
            raise ApiError("invalid_request")
        raw, name, date_order = await upload.read(), upload.filename or "chat.txt", form.get("date_order") or None
    else:
        try:
            body = await request.json()
        except ValueError as exc:
            raise ApiError("invalid_request") from exc
        if not isinstance(body, dict):
            raise ApiError("invalid_request")
        date_order = body.get("date_order")
        if isinstance(body.get("sample"), str):
            try:
                raw, name = load_sample(body["sample"]), f"{body['sample']}.txt"
            except KeyError as exc:
                raise ApiError("not_found") from exc
        elif isinstance(body.get("text"), str):
            raw, name, origin = body["text"].encode("utf-8"), "pasted text", "paste"
        else:
            raise ApiError("invalid_request")
    if date_order not in DATE_ORDERS:
        raise ApiError("invalid_request")
    if len(raw) > ctx.settings.max_import_bytes:
        raise ApiError("too_large")
    chat, media = raw, {}
    if raw[:2] == b"PK" or name.lower().endswith(".zip"):
        export = read_export_zip(raw, max_total_bytes=ctx.settings.max_import_bytes)
        chat, media = export.chat_text, export.media
    summary = build_preview(chat, name, max_bytes=ctx.settings.max_import_bytes, date_order=date_order)
    summary = dataclasses.replace(summary, export_digest=hashlib.sha256(raw).hexdigest())  # the file as given (INTEGRITY_SPEC 4.1)
    return _payload(ctx.add_preview(Preview(chat=chat, raw=raw, file_name=name, origin=origin, media=media)), summary)


@router.post("/ingest/commit")
def commit(body: Commit, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    pending = ctx.previews.get(body.preview_id)
    if pending is None:
        raise ApiError("not_found")
    if body.playbook_key not in ctx.playbooks:
        raise ApiError("invalid_request")
    if body.deal_id is not None:
        deal_of(vault, body.deal_id)
    parsed = parse_export(pending.chat, date_order=body.date_order)
    try:
        draft = prepare_commit(parsed, me=body.me, counterparty=body.counterparty, playbook_key=body.playbook_key,
                               origin=MessageOrigin(pending.origin), deal_id=body.deal_id)
    except SelectionError as exc:
        raise ApiError("bad_selection") from exc
    deal_id = vault.commit_import(draft, export_bytes=pending.raw, file_name=pending.file_name, media=pending.media,
                                  playbook_version=ctx.playbooks[body.playbook_key].version, date_order=parsed.date_order)
    ctx.previews.pop(body.preview_id, None)
    reanalyse(ctx, vault, deal_id)
    return {"deal_id": deal_id, "score": record(ctx, vault, deal_id, "import").score.score}


@router.post("/deals/{deal_id}/messages")
def add_message(deal_id: str, body: Simulated, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """The built-in simulator (FR-IMP-008): a typed message is stored like an imported one and analysed again."""
    deal = deal_of(vault, deal_id)
    if body.sender not in (deal.me_id, deal.counterparty_id):
        raise ApiError("invalid_request")
    before = score_now(ctx, vault, deal_id)
    message = vault.add_message(deal_id, body.sender, body.text)
    reanalyse(ctx, vault, deal_id)
    after = record(ctx, vault, deal_id, "message_added").score.score
    return {**message.model_dump(mode="json"), "score_before": before, "score_after": after}
