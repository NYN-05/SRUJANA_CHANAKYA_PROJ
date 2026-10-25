"""The agreement: versions, the recap and the echo-code reply check, the receipt (S6, S7, S8, S12)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from packages.contracts import AgreedTerm, ConfirmationState
from packages.ingest.recap import build_recap
from packages.vault import Vault, VersionRecord

from ..errors import ApiError
from ..pipeline import deal_of, record, score_now
from ..state import AppContext, current_vault, get_ctx

router = APIRouter()
DISCLAIMER = "Drafting aid, not legal advice. Please read each line before confirming."
LIMIT_TEXT = "This checks that the record was not changed after it was saved. It cannot prove that the original chat export was genuine."
CLOCK_NOTE = "The time shown comes from this device's clock. It can be wrong until the record is anchored."


class RecapBody(BaseModel):
    language: Literal["en", "hi"] = "en"  # Kannada arrives with P1 (Phase 11d)


class ReplyBody(BaseModel):
    text: str
    sender: str | None = None


class VersionBody(BaseModel):
    reason_message_id: str | None = None


def _version(v: VersionRecord, confirmed: bool) -> dict[str, Any]:
    return {
        "n": v.n,
        "created_at": v.created_at,
        "leaf_count": v.leaf_count,
        "term_count": len(v.terms_set["terms"]),
        "terms_digest": v.terms_digest.hex(),
        "root": v.root.hex(),
        "link": v.link.hex(),
        "prev_link": v.prev_link.hex() if v.prev_link else None,
        "reason_message_id": v.reason_message_id,
        "confirmed": confirmed,
    }


@router.post("/deals/{deal_id}/versions")
def create_version(deal_id: str, body: VersionBody | None = None, vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """A new version of the confirmed terms. Earlier versions stay as they were (FR-VER-001)."""
    return _version(vault.create_version(deal_id, body.reason_message_id if body else None), False)


@router.get("/deals/{deal_id}/versions")
def versions(deal_id: str, vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    deal_of(vault, deal_id)
    return {"versions": [_version(v, vault.version_confirmed(deal_id, v.n)) for v in vault.versions(deal_id)]}


@router.get("/deals/{deal_id}/versions/diff")
def diff(deal_id: str, a: int, b: int, vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    return {"rows": [
        {"key": r.key, "a_value": r.a_value.model_dump(mode="json") if r.a_value else None,
         "b_value": r.b_value.model_dump(mode="json") if r.b_value else None, "change": r.change}
        for r in vault.diff_versions(deal_id, a, b)
    ]}


@router.post("/deals/{deal_id}/recap")
def make_recap(deal_id: str, body: RecapBody | None = None, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """The recap of the latest version, in English or Hindi, with its echo code (S6, S12). The person copies and sends it."""
    deal = deal_of(vault, deal_id)
    saved = vault.versions(deal_id)
    if not saved:
        raise ApiError("nothing_to_version")
    version = saved[-1]
    terms = {t["key"]: AgreedTerm.model_validate({**t, "origin": "rules"}) for t in version.terms_set["terms"]}
    other = next(p.display_name for p in vault.participants(deal_id) if p.id == deal.counterparty_id)
    language = body.language if body else "en"
    draft = build_recap(terms, ctx.playbooks[deal.playbook_key], language, other, deal_id=deal_id, version_n=version.n)
    recap = vault.create_recap(deal_id, version.n, draft)
    return {
        "id": recap.id,
        "version_n": recap.version_n,
        "language": recap.language,
        "lines": [line.model_dump(mode="json") for line in recap.lines],
        "omitted_terms": [{"key": key, "reason": reason} for key, reason in recap.omitted_terms],
        "echo_code": recap.echo_code,
        "text": recap.text,
        "disclaimer": DISCLAIMER,
    }


@router.post("/deals/{deal_id}/recaps/{recap_id}/approve")
def approve(deal_id: str, recap_id: str, vault: Vault = Depends(current_vault)) -> dict[str, bool]:
    """The user's own approval; the version is confirmed only when the other side's reply also checks out."""
    vault.approve_recap(recap_id)
    return {"approved": True}


@router.post("/deals/{deal_id}/recaps/{recap_id}/check-reply")
def check_reply(deal_id: str, recap_id: str, body: ReplyBody, ctx: AppContext = Depends(get_ctx), vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    """Check the reply the person pasted. A failed check is a normal answer (state ``not_confirmed``), not an error."""
    before = score_now(ctx, vault, deal_id)
    try:
        result = vault.check_reply(recap_id, body.text, body.sender)
    except ValueError as exc:
        raise ApiError("sender_required") from exc
    after = record(ctx, vault, deal_id, "recap_confirmed").score.score if result.state == ConfirmationState.CONFIRMED else before
    return {**result.model_dump(mode="json"), "score_before": before, "score_after": after}


@router.get("/deals/{deal_id}/receipt")
def receipt(deal_id: str, vault: Vault = Depends(current_vault)) -> dict[str, Any]:
    r = vault.build_receipt(deal_id)
    return {"body": r.body, "receipt_hash": r.receipt_hash.hex(), "limit_text": LIMIT_TEXT, "clock_note": CLOCK_NOTE}
