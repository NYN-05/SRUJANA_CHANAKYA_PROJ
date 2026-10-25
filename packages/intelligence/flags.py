"""Flags with plain reasons (FR-FLG-001 to 003, 005, 006; FR-PBK-003).

Reasons come from the playbook's ambiguity rules and legal hints, or from the fixed per-type templates in
``playbooks/templates/<lang>/flags.yaml``. TEXT_VOICE_CONTRADICTION belongs to Phase 11a.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from packages.contracts import (
    DateValue,
    EventValue,
    Flag,
    FlagType,
    Message,
    MoneyValue,
    PartyValue,
    PaymentValue,
    ProposedTerm,
    QuantityValue,
    SourceRef,
    TermState,
    TextValue,
)
from packages.contracts.formatting import format_date, format_inr

from .ack import acknowledged_keys
from .playbooks import Playbook
from .templates import load_yaml

LANGS = ("en", "hi")


def describe(value: object, lang: str) -> str:
    """A term value in plain words for a reason ("₹50,000", "15 Nov 2026", "200 shirts")."""
    if isinstance(value, (MoneyValue, PaymentValue)) and value.paise is not None:
        suffix = {"item": {"en": " each", "hi": " प्रति नग"}, "total": {"en": " in total", "hi": " कुल"}}.get(getattr(value, "per", None))
        return format_inr(value.paise) + (suffix[lang] if suffix else "")
    if isinstance(value, DateValue):
        return format_date(value.date, lang)
    if isinstance(value, QuantityValue):
        return f"{value.amount} {value.unit or ''}".strip()
    if isinstance(value, TextValue):
        return value.text
    if isinstance(value, PartyValue):
        return ", ".join(value.names)
    if isinstance(value, EventValue):
        return value.event
    return ""  # nothing sensible to show (a payment with no amount, a partial date, nothing at all)


def _label(playbook: Playbook, key: str, lang: str) -> str:
    return playbook.term(key).label[lang]


def _fill(lang: str, name: str, **slots: str) -> str:
    return str(load_yaml(lang, "flags.yaml")[name]).format(**slots)


def _both(name: str, **slots_by_lang: dict[str, str]) -> tuple[str, str]:
    en, hi = (_fill(lang, name, **{k: v[lang] for k, v in slots_by_lang.items()}) for lang in LANGS)
    return en, hi


def build_flags(
    terms: Sequence[ProposedTerm],
    playbook: Playbook,
    messages: Sequence[Message],
    *,
    me_id: str,
    counterparty_id: str,
    names: Mapping[str, str] | None = None,
) -> list[Flag]:
    """Flags for a set of proposed terms. ``names`` maps participant ids to display names for reasons."""
    shown = names or {}
    sender_of = {m.id: m.sender_id for m in messages}
    acked = acknowledged_keys(terms, messages, me_id=me_id, counterparty_id=counterparty_id, window=playbook.ack_window)
    required = set(playbook.required_keys)
    flags: list[Flag] = []

    def add(ftype: FlagType, term: ProposedTerm | None, reason: tuple[str, str], rule_id: str, refs: Sequence[SourceRef]) -> None:
        flags.append(Flag(type=ftype, term_key=term.key if term else None, reason_en=reason[0], reason_hi=reason[1],
                          source_refs=list(refs), rule_id=rule_id))

    for term in terms:
        label = {lang: _label(playbook, term.key, lang) for lang in LANGS}
        label_l = {"en": label["en"].lower(), "hi": label["hi"]}
        if term.state == TermState.MISSING and term.key in required:
            add(FlagType.MISSING_TERM, term, _both("missing_term", label=label, label_l=label_l), "missing_term", [])
        elif term.state == TermState.UNCLEAR:
            rule = playbook.rule(term.unclear_reason or "")
            if rule:
                add(FlagType(rule.type), term, (rule.reason["en"], rule.reason["hi"]), rule.id, term.sources)
            elif not term.needs_review:
                add(FlagType.NEEDS_REVIEW, term, _both("needs_review", label=label, label_l=label_l), "needs_review", term.sources)
        elif term.state == TermState.CONTRADICTED:
            items = {
                lang: _fill(lang, "contradiction_joiner").join(
                    _fill(lang, "contradiction_item", value=describe(c.value, lang), seq=str(min(s.seq for s in c.sources)))
                    for c in term.candidates
                )
                for lang in LANGS
            }
            add(FlagType.CONTRADICTION, term, _both("contradiction", label=label, items=items), "contradiction", term.sources)
        if term.needs_review and term.state != TermState.MISSING:
            add(FlagType.NEEDS_REVIEW, term, _both("needs_review", label=label, label_l=label_l), "needs_review", term.sources)
        if term.state == TermState.STATED and term.sources and term.key not in acked:
            senders = {sender_of.get(s.message_id) for s in term.sources}
            if len(senders) == 1:
                who = {lang: shown.get(next(iter(senders)) or "", next(iter(senders)) or "") for lang in LANGS}
                reason = _both("unacknowledged_one", label=label, label_l=label_l, name=who)
            else:
                reason = _both("unacknowledged_none", label=label, label_l=label_l)
            add(FlagType.UNACKNOWLEDGED, term, reason, "unacknowledged", term.sources)

    # deal-level hints: keywords in the chat, or a named term that was never found
    chat = [m for m in messages if not m.is_system and m.sender_id in (me_id, counterparty_id)]
    state = {t.key: t.state for t in terms}
    for hint in playbook.legal_hints:
        refs: list[SourceRef] = []
        for word in hint.keywords:
            pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)
            found = next(((m, pattern.search(m.text)) for m in chat if pattern.search(m.text)), None)
            if found and found[1]:
                m, hit = found
                refs.append(SourceRef(message_id=m.id, seq=m.seq, start=hit.start(), end=hit.end(), quote=hit.group()))
                break
        missing = hint.term_missing is not None and state.get(hint.term_missing, TermState.MISSING) == TermState.MISSING
        if refs or missing:
            flags.append(Flag(type=FlagType.REGISTRATION_HINT, term_key=None, reason_en=hint.text["en"], reason_hi=hint.text["hi"],
                              source_refs=refs, rule_id=hint.id))
    return flags
