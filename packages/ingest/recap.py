"""Recap drafts from confirmed terms and fixed templates (FR-RCP-001 to 004, ADR-010, I-07).

Computes no hashes (dependency rule 1): the vault turns a draft into a ``Recap`` with its hash and echo code.
Templates are data in ``playbooks/templates/<lang>/<template_set>.recap.yaml``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from packages.contracts import (
    AgreedTerm,
    DateValue,
    MoneyValue,
    PartyValue,
    PaymentValue,
    QuantityValue,
    RecapDraft,
    RecapLine,
    TextValue,
)
from packages.contracts.formatting import format_date, format_inr
from packages.contracts.templates import LANGUAGES, load_yaml


def _slot(value: Any, lang: str) -> str:
    """A confirmed value as plain text; empty when it has nothing to show (the line is then left out)."""
    if isinstance(value, (MoneyValue, PaymentValue)):
        return format_inr(value.paise) if value.paise else ""
    if isinstance(value, DateValue):
        return format_date(value.date, lang)
    if isinstance(value, QuantityValue):
        return str(value.amount)
    if isinstance(value, TextValue):
        return value.text
    if isinstance(value, PartyValue):
        return ", ".join(value.names)
    return getattr(value, "event", "")


def _variant(value: Any) -> str:
    if isinstance(value, PaymentValue):
        if value.when == "after_delivery" and value.days:
            return "after_delivery_days"
        return value.when or "plain"
    if isinstance(value, MoneyValue):
        return value.per or "plain"
    return "plain"


def _extra_slots(values: Mapping[str, Any], lang: str) -> dict[str, str]:
    """{total} = quantity x unit price (or the price itself); {days} and {date} from a payment value."""
    out: dict[str, str] = {}
    price, quantity = values.get("price"), values.get("quantity")
    if isinstance(price, MoneyValue):
        if price.per == "total":
            out["total"] = format_inr(price.paise)
        elif isinstance(quantity, QuantityValue):
            out["total"] = format_inr(int(price.paise) * quantity.amount)
    for value in values.values():
        if isinstance(value, PaymentValue):
            if value.days:
                out.setdefault("days", str(value.days))
            if value.date:
                out.setdefault("date", format_date(value.date, lang))
    return out


def build_recap(
    terms: Mapping[str, AgreedTerm], playbook: Any, language: str, other_name: str, *, deal_id: str, version_n: int
) -> RecapDraft:
    """Lines only for confirmed terms. A line that lacks a term, or a value it can show, is left out and its
    terms are listed in ``omitted_terms`` (``not_confirmed`` or ``incomplete_line``). Required terms that are
    not confirmed are listed too."""
    if language not in LANGUAGES:
        raise ValueError(f"no recap templates for language {language!r}")
    templates = load_yaml(language, f"{playbook.recap_template_set}.recap.yaml")
    values = {key: term.value for key, term in terms.items()}
    slots = {key: text for key, v in values.items() if (text := _slot(v, language))}

    lines: list[RecapLine] = []
    omitted: dict[str, str] = {}
    required = {t.key for t in playbook.terms if t.required}
    for entry in templates["lines"]:
        needed = entry["terms"]
        missing = [k for k in needed if k not in terms]
        if missing:
            for k in needed:
                omitted.setdefault(k, "not_confirmed" if k in missing else "incomplete_line")
            continue
        variant = _variant(values[entry["variant_from"]]) if "variant_from" in entry else "plain"
        first = values[needed[0]]
        no_amount = isinstance(first, (MoneyValue, PaymentValue)) and not first.paise
        chosen = next((entry["templates"][v] for v in ((f"noamt_{variant}",) if no_amount else ()) + (variant, "plain") if v in entry["templates"]), None)
        try:
            text = chosen.format_map({**slots, **_extra_slots({k: values[k] for k in needed}, language)}) if chosen else None
        except KeyError:
            text = None
        if text is None:
            omitted.update({k: "incomplete_line" for k in needed})
            continue
        sources = list(dict.fromkeys(s.message_id for k in needed for s in terms[k].sources))
        lines.append(RecapLine(term_key=entry["key"], text=text, sources=sources))

    omitted = {k: r for k, r in omitted.items() if r != "not_confirmed" or k in required}  # optional terms are not nagged
    omitted.update({k: "not_confirmed" for k in required if k not in terms and k not in omitted})
    order = {t.key: i for i, t in enumerate(playbook.terms)}
    bullet = templates.get("bullet", "• ")
    body = "\n".join([templates["greeting"].format(other_name=other_name), *(bullet + line.text for line in lines)])
    return RecapDraft(
        deal_id=deal_id,
        version_n=version_n,
        language=language,
        lines=lines,
        body_text=body,
        omitted_terms=sorted(omitted.items(), key=lambda kv: order.get(kv[0], 99)),
        closing=templates["closing"],
    )


def build_whatsapp_message(recap: Any) -> str:
    """The text the user copies into WhatsApp: greeting, bullet lines and the closing line with the code."""
    return recap.body_text + "\n" + recap.closing.replace("{code}", recap.echo_code)
