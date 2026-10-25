"""The one suggested next message (FR-SUG-001 to 004; I-05). The user always sends it: nothing here sends."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from functools import lru_cache
from typing import Any

from packages.contracts import MoneyValue, QuantityValue, Suggestion, TermState, Tone
from packages.contracts.formatting import format_inr

from .flags import describe
from .playbooks import Playbook
from .score import ScoreInput, factor
from .templates import TemplateMissing, load_yaml

__all__ = ["TemplateMissing", "build_suggestion", "choose_targets", "load_templates", "rank_gaps"]

_SLOT = re.compile(r"\{(\w+)\}")
# Computed slots: name -> (term key the user must fill in, bracket label by language)
_COMPUTED = {"balance": ("final_payment", {"en": "balance", "hi": "बाकी रकम"})}


def rank_gaps(inputs: Sequence[ScoreInput], playbook: Playbook) -> list[tuple[str, Decimal]]:
    """Required terms with gain > 0: conflicts first, then gain = weight x (1 - factor) descending, then ask order."""
    by_key = {i.key: i for i in inputs}
    rows = []
    for term in (t for t in playbook.terms if t.required):
        item = by_key.get(term.key)
        gain = Decimal(term.weight) * (1 - factor(item))
        if gain > 0:
            conflict = item is not None and item.state == TermState.CONTRADICTED
            rows.append((not conflict, -gain, term.ask_order, term.key, gain))
    return [(key, gain) for *_, key, gain in sorted(rows)]


def choose_targets(inputs: Sequence[ScoreInput], playbook: Playbook) -> list[str]:
    """The top gap, plus one partner from its ``pairs_with`` when that partner is also a gap (at most two)."""
    ranked = [key for key, _ in rank_gaps(inputs, playbook)]
    if not ranked:
        return []
    partner = next((p for p in playbook.term(ranked[0]).pairs_with if p in ranked), None)
    return [ranked[0]] + ([partner] if partner else [])


@lru_cache(maxsize=None)
def load_templates(playbook_key: str, language: str) -> dict[str, Any]:
    """``{"<sorted target keys joined by +>": {"casual": ..., "polite": ..., "firm": ...}}``."""
    return load_yaml(language, f"{playbook_key}.suggest.yaml")


def _paise(value: object) -> int | None:
    paise = getattr(value, "paise", None)
    return int(paise) if paise else None


def _balance(values: Mapping[str, Any]) -> int | None:
    """Total minus advance when both are known; else the balance if it was stated."""
    price, quantity, advance = values.get("price"), values.get("quantity"), _paise(values.get("advance"))
    total = None
    if isinstance(price, MoneyValue):
        if price.per == "total":
            total = int(price.paise)
        elif isinstance(quantity, QuantityValue):
            total = int(price.paise) * quantity.amount
    if total is not None and advance is not None and total >= advance:
        return total - advance
    return _paise(values.get("final_payment"))


def build_suggestion(targets: Sequence[str], tone: Tone, values: Mapping[str, Any], playbook: Playbook, language: str) -> Suggestion:
    """Fill the template for these targets. Unknown facts become ``[label]`` and are listed in ``needs_user_input``."""
    templates = load_templates(playbook.key, language)
    key = "+".join(sorted(targets))
    used = list(targets)
    node = templates.get(key)
    if node is None:  # no pair template: fall back to the single-term template of the top target
        node, used = templates.get(targets[0]), [targets[0]]
    if not node or tone.value not in node:
        raise TemplateMissing(key, tone.value, language)

    missing: list[str] = []

    def slot(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _COMPUTED:
            owner, labels = _COMPUTED[name]
            amount = _balance(values)
            text, label = (format_inr(amount) if amount is not None else ""), labels[language]
        else:
            owner = name
            text = describe(values[name], language) if values.get(name) is not None else ""
            label = playbook.term(name).label[language].lower() if name in playbook._by_key else name.replace("_", " ")
        if text:
            return text
        if owner not in missing and owner in playbook._by_key:
            missing.append(owner)
        return f"[{label}]"

    text = _SLOT.sub(slot, node[tone.value])
    return Suggestion(target_term_keys=used, tone=tone, language=language, text=text, needs_user_input=missing)
