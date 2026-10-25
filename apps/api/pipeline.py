"""The analysis pipeline behind the routes: rules, optional model refinement, flags, acknowledgement, score, suggestion.

Everything here is deterministic apart from the optional model, whose result is checked by the packages. Results are
rebuilt from the vault each time, so a restart loses nothing (FR-SCO-003: recompute after import, a term action, a
new simulator message and a recap confirmation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.contracts import AgreedTerm, Flag, Message, ProposedTerm, ScoreResult, Suggestion, TermState, Tone
from packages.contracts import TERM_STATE_LABELS
from packages.intelligence.ack import acknowledged_keys
from packages.intelligence.extract import extract_terms
from packages.intelligence.flags import build_flags
from packages.intelligence.model.models import analysis_mode
from packages.intelligence.model.refine import RefineResult, refine_terms
from packages.intelligence.playbooks import Playbook
from packages.intelligence.score import ScoreInput, compute_score
from packages.intelligence.suggest import build_suggestion, choose_targets
from packages.vault import Deal, Vault

from .errors import ApiError
from .state import AppContext

MODEL_TIMEOUT_S = 10  # NFR-PERF-004 target; the rules result is shown first


@dataclass
class Snapshot:
    deal: Deal
    playbook: Playbook
    messages: list[Message]
    terms: list[ProposedTerm]  # what the person sees: agreed terms count as clear
    agreed: dict[str, AgreedTerm]
    flags: list[Flag]
    inputs: list[ScoreInput]
    score: ScoreResult


def deal_of(vault: Vault, deal_id: str) -> Deal:
    deal = next((d for d in vault.deals() if d.id == deal_id), None)
    if deal is None:
        raise ApiError("not_found")
    return deal


def _eligible(messages: list[Message], deal: Deal) -> set[str]:
    parties = {deal.me_id, deal.counterparty_id}
    return {m.id for m in messages if not m.is_system and m.sender_id in parties}


def mode_of(ctx: AppContext) -> tuple[str, str | None]:
    """(``rules_only`` | ``rules_and_ai``, reason). The switch is read here, on every call."""
    return analysis_mode(ctx.safe_mode, ctx.model()[0])


def rules_result(vault: Vault, ctx: AppContext, deal_id: str) -> tuple[Deal, Playbook, list[Message], list[ProposedTerm]]:
    deal = deal_of(vault, deal_id)
    playbook = ctx.playbooks[deal.playbook_key]
    messages = vault.messages(deal_id)
    terms = extract_terms(messages, playbook, me_id=deal.me_id, counterparty_id=deal.counterparty_id,
                          date_order=deal.date_order or "DMY", eligible_ids=_eligible(messages, deal))
    return deal, playbook, messages, terms


def refined(ctx: AppContext, deal: Deal, playbook: Playbook, messages: list[Message], rules: list[ProposedTerm]) -> RefineResult | None:
    """The model's refinement, or None when safe mode is on or the model is unavailable. Never raises for model trouble."""
    if mode_of(ctx)[0] != "rules_and_ai":
        return None
    return refine_terms(rules, messages, playbook, ctx.model()[1], timeout_s=MODEL_TIMEOUT_S, me_id=deal.me_id,
                        counterparty_id=deal.counterparty_id, eligible_ids=_eligible(messages, deal))


def reanalyse(ctx: AppContext, vault: Vault, deal_id: str) -> list[ProposedTerm]:
    """Run the rules (and the model unless safe mode) on the current messages and store the proposals."""
    deal, playbook, messages, rules = rules_result(vault, ctx, deal_id)
    result = refined(ctx, deal, playbook, messages, rules)
    terms = result.terms if result else rules
    vault.save_proposals(deal_id, terms)
    return terms


def _effective(proposal: ProposedTerm, agreed: AgreedTerm | None) -> ProposedTerm:
    if agreed is None:
        return proposal
    return proposal.model_copy(update={"value": agreed.value, "state": TermState.STATED, "sources": agreed.sources, "candidates": [],
                                       "origin": agreed.origin, "needs_review": False, "unclear_reason": None, "readings": [],
                                       "confidence": "high"})


def snapshot(ctx: AppContext, vault: Vault, deal_id: str, proposed: list[ProposedTerm] | None = None) -> Snapshot:
    """Everything the screens show, from the stored proposals (or from ``proposed``, such as a fresh rules result)."""
    deal = deal_of(vault, deal_id)
    playbook = ctx.playbooks[deal.playbook_key]
    messages = vault.messages(deal_id)
    proposals = {t.key: t for t in proposed} if proposed is not None else vault.proposals(deal_id)
    agreed = vault.agreed_terms(deal_id)
    ordered = [proposals[t.key] for t in playbook.terms if t.key in proposals]
    terms = [_effective(p, agreed.get(p.key)) for p in ordered]
    acked = acknowledged_keys(ordered, messages, me_id=deal.me_id, counterparty_id=deal.counterparty_id, window=playbook.ack_window)
    flags = build_flags(terms, playbook, messages, me_id=deal.me_id, counterparty_id=deal.counterparty_id)
    inputs = [
        ScoreInput(
            key=t.key,
            confirmed=t.key in agreed,
            state=TermState.STATED if t.key in agreed else (proposals[t.key].state if t.key in proposals else TermState.MISSING),
            acknowledged_by_both=t.key in agreed and (t.key in acked or agreed[t.key].acknowledged_by_other),
        )
        for t in playbook.terms
    ]
    return Snapshot(deal, playbook, messages, terms, agreed, flags, inputs, compute_score(inputs, playbook))


def score_now(ctx: AppContext, vault: Vault, deal_id: str) -> int:
    return snapshot(ctx, vault, deal_id).score.score


def record(ctx: AppContext, vault: Vault, deal_id: str, trigger: str) -> Snapshot:
    """Snapshot the score under the trigger that caused it (FR-SCO-003)."""
    snap = snapshot(ctx, vault, deal_id)
    vault.record_score(deal_id, snap.score, trigger)
    return snap


def suggest(snap: Snapshot, tone: Tone, language: str) -> Suggestion | None:
    targets = choose_targets(snap.inputs, snap.playbook)
    if not targets:
        return None
    values = {key: term.value for key, term in snap.agreed.items()}
    return build_suggestion(targets, tone, values, snap.playbook, language)


def term_payload(term: ProposedTerm, agreed: dict[str, AgreedTerm], playbook: Playbook) -> dict[str, Any]:
    """A term for the screens: its label is a symbol and a word; ``type`` and ``name`` tell the screen what to ask for."""
    symbol, word = TERM_STATE_LABELS[term.state]
    spec = playbook.term(term.key)
    data = term.model_dump(mode="json")
    data.update(label=f"{symbol} {word}", confirmed=term.key in agreed, type="payment" if "payment" in spec.parsers else spec.type,
                name=spec.label["en"], name_hi=spec.label["hi"], required=spec.required)
    return data


def score_payload(score: ScoreResult) -> dict[str, Any]:
    return {
        "score": score.score,
        "present_count": score.present_count,
        "clear_count": score.clear_count,
        "acknowledged_count": score.acknowledged_count,
        "total": score.total,
        "rows": [{"key": r.key, "weight": int(r.weight), "present": r.present, "clear": r.clear, "acknowledged": r.acknowledged,
                  "points": float(r.points)} for r in score.rows],
    }
