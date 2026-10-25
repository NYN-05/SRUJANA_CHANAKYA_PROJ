"""The grounding check (AI_SPEC section 5; FR-AIS-002): a model term is kept only if deterministic code can trace it
to real, eligible, non-injected chat text. Checks run in this order, and the first failure is the reason:
``unknown_source``, ``ineligible_source``, ``injection_source``, ``quote_not_found``, ``value_not_derivable``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from packages.contracts import (
    DateValue,
    Message,
    MoneyValue,
    PartialDateValue,
    PartyValue,
    PaymentValue,
    PercentValue,
    ProposedTerm,
    QuantityValue,
    TextValue,
)

from ..injection import is_injection
from ..normalize import normalize_for_rules
from ..rules import parse_amounts, parse_dates, parse_payment_phrases, parse_percentages, parse_quantities
from .output import ModelTerm

_WHEN = {"on_delivery": "on_delivery", "after_delivery": "after_delivery", "on_completion": "on_completion"}


@dataclass(frozen=True)
class GroundingFailure:
    term: ModelTerm
    reason: str


def compatible(a: Any, b: Any) -> bool:
    """Same kind of value, and every field both sides state is equal ("₹48,000" fits "₹48,000, paid")."""
    if a is None or b is None or type(a) is not type(b):
        return False
    return all(getattr(a, f) in (None, getattr(b, f)) or getattr(b, f) is None for f in type(a).model_fields if f != "kind")


def _derived(quote: str, reference: date) -> list[Any]:
    """Every value the rules parsers can read out of a quote."""
    out: list[Any] = []
    for a in parse_amounts(quote):
        if a.paise is not None:
            out += [MoneyValue(paise=str(a.paise), per=a.per), PaymentValue(paise=str(a.paise))]
    out += [QuantityValue(amount=q.amount, unit=q.unit) for q in parse_quantities(quote) if q.amount is not None]
    out += [PercentValue(basis_points=p.basis_points) for p in parse_percentages(quote)]
    for p in parse_payment_phrases(quote):
        if p.kind in _WHEN:
            out.append(PaymentValue(when=_WHEN[p.kind]))  # type: ignore[arg-type]
        elif p.kind == "net_days":
            out.append(PaymentValue(when="after_delivery", days=p.days))
    for d in parse_dates(quote, reference=reference, date_order=None):
        for day in ([d.value] if d.value else []) + list(d.readings):
            out += [DateValue(date=day.isoformat()), PartialDateValue(date=f"--{day.month:02d}-{day.day:02d}")]
    return out


def _grounded_value(term: ModelTerm, cited: list[Message], quote: str, rules: Sequence[ProposedTerm], parties: set[str]) -> bool:
    value = term.value
    if value is None:
        return False
    if isinstance(value, PartyValue):
        return set(value.names) <= parties
    cited_ids = {m.id for m in cited}
    for rule in rules:  # equal to a rules value from the same source
        if rule.key == term.key and rule.value is not None and cited_ids & {s.message_id for s in rule.sources}:
            if compatible(value, rule.value) or any(compatible(value, c.value) for c in rule.candidates):
                return True
    if isinstance(value, TextValue):
        said = normalize_for_rules(value.text).lower()
        return bool(said) and (said in normalize_for_rules(quote).lower() or normalize_for_rules(quote).lower() in said)
    reference = datetime.fromisoformat(cited[0].ts).date()
    return any(compatible(value, candidate) for candidate in _derived(quote, reference))


def ground_terms(
    model_terms: Sequence[ModelTerm],
    messages: Sequence[Message],
    rule_terms: Sequence[ProposedTerm],
    *,
    me_id: str,
    counterparty_id: str,
    eligible_ids: set[str] | None = None,
) -> tuple[list[ModelTerm], list[GroundingFailure]]:
    """``(accepted, failures)``. Failures are counted and returned, never hidden."""
    by_seq = {m.seq: m for m in messages}
    parties = {me_id, counterparty_id}
    accepted: list[ModelTerm] = []
    failures: list[GroundingFailure] = []
    for term in model_terms:
        cited = [by_seq.get(s) for s in term.source_seqs]
        reason = None
        if not cited or any(m is None for m in cited):
            reason = "unknown_source"
        else:
            usable = [m for m in cited if m is not None and not m.is_system and m.sender_id in parties
                      and (eligible_ids is None or m.id in eligible_ids)]
            clean = [m for m in usable if not is_injection(m.text)]
            if not usable:
                reason = "ineligible_source"
            elif not clean:
                reason = "injection_source"
            else:
                quote = normalize_for_rules(term.quote).lower()
                if not quote or not any(quote in normalize_for_rules(m.text).lower() for m in clean):
                    reason = "quote_not_found"
                elif not _grounded_value(term, clean, term.quote, rule_terms, parties):
                    reason = "value_not_derivable"
        if reason:
            failures.append(GroundingFailure(term, reason))
        else:
            accepted.append(term)
    return accepted, failures
