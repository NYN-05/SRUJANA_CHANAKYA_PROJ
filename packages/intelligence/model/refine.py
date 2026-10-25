"""Refine the rules result with a model, without ever trusting it (FR-EXT-004, FR-AIS-001 to 004, AI_SPEC sections 7 and 10).

The model can only add or question a proposal. Every proposal it makes passes ``ground_terms`` first, and every failure
(timeout, exception, bad output) leaves the rules result standing with ``error`` set. Log lines carry codes only.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from packages.contracts import Candidate, Message, Origin, ProposedTerm, SourceRef, TermState

from .grounding import compatible, ground_terms
from .output import ModelTerm, parse_model_output
from .port import ModelRunner
from .prompt import build_prompt

log = logging.getLogger("veridoc.model")


@dataclass(frozen=True)
class RefineResult:
    terms: list[ProposedTerm]
    grounding_failures: int
    dropped: int  # model entries discarded before grounding (unknown key, unreadable value) or not a proposal
    used_model: bool
    error: str | None  # timeout | runner_error | invalid_output


def _call(runner: ModelRunner, prompt: Any, timeout_s: float) -> str:
    """Run the model in a helper thread so the answer comes back within the budget even if the model keeps working."""
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["out"] = runner.generate(prompt.system, prompt.data_block, prompt.schema, timeout_s)
        except BaseException as exc:  # a MemoryError in the thread must not escape it
            box["err"] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise TimeoutError
    if "err" in box:
        raise box["err"]
    return str(box["out"])


def _sources(term: ModelTerm, messages: Sequence[Message]) -> list[SourceRef]:
    by_seq = {m.seq: m for m in messages}
    out = []
    for seq in term.source_seqs:
        m = by_seq[seq]
        start = m.text.lower().find(term.quote.lower())
        start, end = (start, start + len(term.quote)) if start >= 0 else (0, len(m.text))
        out.append(SourceRef(message_id=m.id, seq=m.seq, start=start, end=end, quote=m.text[start:end]))
    return out


def _merge(rule: ProposedTerm, model: ModelTerm, messages: Sequence[Message]) -> ProposedTerm:
    """Rules and one grounded model term for the same key (AI_SPEC section 7)."""
    if model.state != TermState.STATED or model.value is None:
        return rule  # a model that is unsure proposes nothing
    sources = _sources(model, messages)
    if rule.state == TermState.STATED and rule.value is not None:
        if compatible(model.value, rule.value):
            return rule.model_copy(update={"origin": Origin.BOTH})
        return rule.model_copy(update={
            "value": None, "state": TermState.UNCLEAR, "needs_review": True, "origin": Origin.BOTH, "unclear_reason": None,
            "candidates": [Candidate(value=rule.value, sources=rule.sources), Candidate(value=model.value, sources=sources)],
        })
    if rule.state == TermState.CONTRADICTED:
        return rule
    return rule.model_copy(update={  # the rules found nothing usable: an AI-only proposal that a person must check
        "value": model.value, "state": TermState.STATED, "origin": Origin.AI, "needs_review": True, "sources": sources,
        "raw": sources[0].quote if sources else None, "candidates": [], "unclear_reason": None, "confidence": "low",
    })


def refine_terms(
    rule_terms: Sequence[ProposedTerm],
    messages: Sequence[Message],
    playbook: Any,
    runner: ModelRunner | None,
    *,
    timeout_s: float,
    me_id: str,
    counterparty_id: str,
    eligible_ids: set[str] | None = None,
) -> RefineResult:
    """The rules terms, refined by the model when it is present, in time and right. Never raises for model problems."""
    rules = list(rule_terms)
    if runner is None:
        return RefineResult(rules, 0, 0, False, None)
    prompt = build_prompt(messages, playbook, eligible_ids=eligible_ids)
    try:
        raw = _call(runner, prompt, timeout_s)
    except TimeoutError:
        log.warning("model_timeout")
        return RefineResult(rules, 0, 0, False, "timeout")
    except Exception as exc:
        log.warning("model_runner_error type=%s", type(exc).__name__)
        return RefineResult(rules, 0, 0, False, "runner_error")
    model_terms, problems = parse_model_output(raw, playbook, messages)
    if any(p.kind == "invalid_json" for p in problems):
        log.warning("model_invalid_output")
        return RefineResult(rules, 0, len(problems), False, "invalid_output")
    usable = [t for t in model_terms if t.value is not None and not t.needs_review]
    accepted, failures = ground_terms(usable, messages, rules, me_id=me_id, counterparty_id=counterparty_id, eligible_ids=eligible_ids)
    first = {}
    for term in accepted:
        first.setdefault(term.key, term)
    refined = [_merge(r, first[r.key], messages) if r.key in first else r for r in rules]
    log.info("model_refined accepted=%d grounding_failures=%d", len(first), len(failures))
    return RefineResult(refined, len(failures), len(problems), True, None)
