"""Turn the model's raw text into typed candidate terms. The output is never trusted (AI_SPEC section 4; I-02, I-03, I-04).

Nothing here raises: a malformed entry becomes a ``needs_review`` term or is dropped with a counted problem.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import ValidationError

from packages.contracts import (
    DateValue,
    Message,
    MoneyValue,
    PartialDateValue,
    PartyValue,
    PaymentValue,
    PercentValue,
    QuantityValue,
    TermState,
    TermValue,
    TextValue,
)

from ..rules import parse_amounts

_STATES = {"stated": TermState.STATED, "unclear": TermState.UNCLEAR, "contradicted": TermState.CONTRADICTED}
_WHEN = {"paid", "on_delivery", "after_delivery", "on_date", "on_completion"}
_NUMBER = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d{1,2})?)", re.IGNORECASE)


@dataclass(frozen=True)
class OutputProblem:
    kind: str  # invalid_json | bad_entry | unknown_key | bad_state | bad_source | bad_value
    detail: str = ""


@dataclass(frozen=True)
class ModelTerm:
    """One candidate term from the model, with a normalised value. It is a suggestion, never a fact."""

    key: str
    value: TermValue | None
    state: TermState
    source_seqs: list[int]
    quote: str
    confidence: float
    needs_review: bool = False
    unit: str | None = None
    problems: list[str] = field(default_factory=list)


def _paise(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    text = str(value).strip().replace(",", "")
    if m := _NUMBER.fullmatch(text):
        return str(int((Decimal(m.group(1)) * 100).to_integral_value(ROUND_HALF_UP)))
    found = parse_amounts(str(value))  # "50k", "1.5 lakh", "pachaas hazaar"
    return str(found[0].paise) if len(found) == 1 and found[0].paise is not None else None


def _per(unit: Any) -> str | None:
    word = str(unit or "").lower()
    return "total" if "total" in word else "item" if any(w in word for w in ("each", "item", "piece", "pc", "unit", "per")) else None


def _normalise(term_type: str, is_payment: bool, value: Any, unit: Any) -> TermValue | None:
    """The contract value for a model value, or None when it cannot be read."""
    try:
        if is_payment:
            if isinstance(value, str) and value.strip().lower() in _WHEN:
                return PaymentValue(when=value.strip().lower())  # type: ignore[arg-type]
            paise = _paise(value)
            return PaymentValue(paise=paise) if paise is not None else None
        if term_type == "money":
            paise = _paise(value)
            return MoneyValue(paise=paise, per=_per(unit)) if paise is not None else None  # type: ignore[arg-type]
        if term_type == "date" and isinstance(value, str):
            text = value.strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                return DateValue(date=text)
            if m := re.fullmatch(r"-{0,2}(\d{2})-(\d{2})", text):
                return PartialDateValue(date=f"--{m.group(1)}-{m.group(2)}")
            return None
        if term_type == "quantity":
            if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"\d+", str(value).strip()):
                return None
            return QuantityValue(amount=int(str(value).strip()), unit=str(unit).strip() or None if unit else None)
        if term_type == "percent":
            m = re.fullmatch(r"(\d+(?:\.\d{1,2})?)\s*%?", str(value).strip())
            return PercentValue(basis_points=int((Decimal(m.group(1)) * 100).to_integral_value(ROUND_HALF_UP))) if m else None
        if term_type == "party":
            names = [n.strip() for n in str(value).split(",") if n.strip()]
            return PartyValue(names=names) if names else None
        if isinstance(value, str) and value.strip():
            return TextValue(text=value.strip())
    except (ValidationError, ValueError, TypeError, ArithmeticError):
        pass
    return None


def parse_model_output(raw: str, playbook: Any, messages: Sequence[Message]) -> tuple[list[ModelTerm], list[OutputProblem]]:
    """``(terms, problems)``. ``messages`` is accepted so a caller can pass the list the prompt was built from."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError, RecursionError):
        return [], [OutputProblem("invalid_json")]
    if not isinstance(data, dict) or not isinstance(data.get("terms"), list):
        return [], [OutputProblem("invalid_json", "no terms list")]
    terms: list[ModelTerm] = []
    problems: list[OutputProblem] = []
    for entry in data["terms"]:
        if not isinstance(entry, dict):
            problems.append(OutputProblem("bad_entry"))
            continue
        key = playbook.key_for_alias(entry["key"]) if isinstance(entry.get("key"), str) else None
        if key is None:
            problems.append(OutputProblem("unknown_key"))
            continue
        review, notes = False, []
        state = _STATES.get(entry.get("state")) if isinstance(entry.get("state"), str) else None
        if state is None:
            state, review = TermState.UNCLEAR, True
            problems.append(OutputProblem("bad_state", key))
            notes.append("bad_state")
        seqs = entry.get("source_seqs")
        if not isinstance(seqs, list) or not all(isinstance(s, int) and not isinstance(s, bool) for s in seqs):
            seqs, review = [], True
            problems.append(OutputProblem("bad_source", key))
            notes.append("bad_source")
        confidence = entry.get("confidence")
        confidence = min(1.0, max(0.0, float(confidence))) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else 0.0
        term = playbook.term(key)
        value = _normalise(term.type, "payment" in term.parsers, entry.get("value"), entry.get("unit"))
        if value is None:
            review = True
            problems.append(OutputProblem("bad_value", key))
            notes.append("bad_value")
        quote = entry.get("quote")
        terms.append(ModelTerm(key, value, state, list(seqs), quote if isinstance(quote, str) else "", confidence, review,
                               str(entry["unit"]) if isinstance(entry.get("unit"), str) else None, notes))
    return terms, problems
