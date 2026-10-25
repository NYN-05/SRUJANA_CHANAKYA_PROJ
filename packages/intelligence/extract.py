"""Rules-only term extraction (FR-EXT-001 to 003; AI_SPEC sections 2 and 3; I-14, I-16, I-23, I-24).

No model, no network, no clock: the reference date comes from each message (or the argument).
What each playbook term collects is decided by the playbook's data, not by its key:

* ``quantities`` parser + type quantity: counted units named in the term's cues; type text: the unit noun
* ``amounts`` + type money: the price (an amount with no payment cue around it)
* ``payment`` parser: a payment term (advance, balance); it owns the clauses that contain its cue words
* ``dates`` + type date: a date in a message that contains one of the term's cue words
* ``penalty`` parser: the sentence that holds a penalty phrase
* other text or enum terms: sentences that contain one of the term's cue words
* type party: the two chosen participants
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from packages.contracts import (
    Candidate,
    DateValue,
    Message,
    MoneyValue,
    Origin,
    PartyValue,
    PaymentValue,
    ProposedTerm,
    QuantityValue,
    SourceRef,
    TermState,
    TextValue,
)

from .injection import is_injection
from .normalize import Normalized, nfc, normalize
from .playbooks import Playbook, Term
from .rules import (
    AmountMatch,
    parse_amounts,
    parse_dates,
    parse_payment_phrases,
    parse_penalty_phrases,
    parse_percentages,
    parse_quantities,
)

_BUILTIN_RULES = {
    "rel_date": "AMBIGUOUS_DATE",
    "partial_date": "AMBIGUOUS_DATE",
    "order_date": "AMBIGUOUS_DATE",
    "approx_amount": "AMBIGUOUS_AMOUNT",
    "vague_qty": "VAGUE_QUANTITY",
    "vague_pay": "VAGUE_PAYMENT",
    "half_adv": "VAGUE_PAYMENT",
}
# Words that mark an amount as a payment already made, and fallbacks when a playbook has no such term.
_PAID_WORDS = ["sent", "paid", "received", "transferred", "bheja", "bhej", "diya", "mila", "mil gaya", "भेजा", "दिया", "मिल गया"]
_FALLBACK_PAYMENT_WORDS = ["advance", "balance", "baaki", "baki", "remaining", "instalment", "milestone", "upfront", "peshgi"]
_FALLBACK_PENALTY_WORDS = ["late", "penalty", "deduct", "deduction", "jurmana"]
_GENERIC_UNITS = {"pcs", "pc", "pieces", "piece", "units", "unit", "items", "item", "nos", "sets", "set"}
_CLAUSE = re.compile(r",(?=\s|$)|;|[!?]|(?<![Rr]s)\.(?=\s|$)")
_SENTENCE = re.compile(r";|[!?]|(?<![Rr]s)\.(?=\s|$)")


@dataclass
class _Cand:
    value: Any  # a TermValue, or None when only vague
    sources: list[SourceRef]
    reason: str | None = None  # playbook ambiguity rule id when the value is unclear
    review: bool = False
    readings: list[Any] = field(default_factory=list)
    key: Any = None  # grouping key; the JSON of the value when None
    kind: str = ""  # price: "unit" or "total"
    pct_bp: int | None = None  # a share of a total that is not known yet


def _cue_re(words: Sequence[str]) -> re.Pattern[str] | None:
    parts = sorted({re.escape(nfc(w)).replace(r"\ ", r"\s+") for w in words if w.strip()}, key=lambda p: (-len(p), p))
    if not parts:
        return None
    return re.compile(rf"(?<![A-Za-z0-9ऀ-෿])(?:{'|'.join(parts)})(?![A-Za-zऀ-෿])", re.IGNORECASE)


@dataclass
class _Scan:
    """One message with everything the parsers found, and helpers to place matches in clauses."""

    msg: Message
    nz: Normalized
    clauses: list[tuple[int, int]]
    sentences: list[tuple[int, int]]

    @classmethod
    def of(cls, msg: Message) -> _Scan:
        nz = normalize(msg.text)
        return cls(msg, nz, _segments(nz.text, _CLAUSE), _segments(nz.text, _SENTENCE))

    def segment(self, segs: list[tuple[int, int]], original_index: int) -> tuple[int, int]:
        i = bisect_right([s for s, _ in segs], self.nz.norm_index(original_index)) - 1
        return segs[max(i, 0)] if segs else (0, 0)

    def text(self, seg: tuple[int, int]) -> str:
        return self.nz.text[seg[0] : seg[1]]

    def source(self, start: int, end: int) -> SourceRef:
        m = self.msg
        return SourceRef(message_id=m.id, seq=m.seq, start=start, end=end, quote=self.nz.original[start:end])

    def segment_source(self, seg: tuple[int, int]) -> SourceRef:
        s, e = seg
        if e <= s:  # no segment (cannot happen for a match); fall back to the whole message
            return self.source(0, len(self.nz.original))
        while s < e and self.nz.text[s] == " ":
            s += 1
        while e > s and self.nz.text[e - 1] == " ":
            e -= 1
        return self.source(self.nz.starts[s], self.nz.ends[e - 1])


def _segments(text: str, boundary: re.Pattern[str]) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in boundary.finditer(text):
        if text[start : m.start()].strip():
            out.append((start, m.start()))
        start = m.end()
    if text[start:].strip():
        out.append((start, len(text)))
    return out


def _reason(playbook: Playbook, rule_id: str) -> str:
    """The playbook's id for an ambiguity: its own rule, else the first rule of the same flag type."""
    if playbook.rule(rule_id):
        return rule_id
    return next((r.id for r in playbook.ambiguity_rules if r.type == _BUILTIN_RULES.get(rule_id)), rule_id)


def _sources(cands: Sequence[_Cand]) -> list[SourceRef]:
    seen: dict[tuple[str, int, int], SourceRef] = {}
    for c in cands:
        for s in c.sources:
            seen.setdefault((s.message_id, s.start, s.end), s)
    return sorted(seen.values(), key=lambda s: (s.seq, s.start))


def _merge_payments(cands: list[_Cand]) -> list[_Cand]:
    """Payment statements that do not contradict each other are one statement ("40,000" + "on delivery")."""
    fields = ("paise", "when", "days", "date")
    merged: list[_Cand] = []
    for c in (c for c in cands if c.value is not None and c.reason is None):
        for g in merged:
            if all(getattr(g.value, f) in (None, getattr(c.value, f)) or getattr(c.value, f) is None for f in fields):
                g.value = PaymentValue(**{f: getattr(g.value, f) if getattr(g.value, f) is not None else getattr(c.value, f) for f in fields})
                g.sources += c.sources
                g.review = g.review or c.review
                break
        else:
            merged.append(_Cand(c.value, list(c.sources), review=c.review))
    return merged + [c for c in cands if c.value is None or c.reason is not None]


def _resolve(term: Term, cands: list[_Cand]) -> ProposedTerm:
    """Stated (one concrete value), contradicted (two or more), unclear (only vague) or missing (I-16)."""
    cands = sorted((c for c in cands if c.sources), key=lambda c: (c.sources[0].seq, c.sources[0].start))
    concrete = [c for c in cands if c.value is not None and c.reason is None]
    vague = [c for c in cands if not (c.value is not None and c.reason is None)]
    groups: list[tuple[Any, list[_Cand]]] = []
    for c in concrete:
        key = c.key if c.key is not None else c.value.model_dump_json()
        if key == () and groups:
            groups[0][1].append(c)
            continue
        if groups and groups[0][0] == () and len(groups) == 1:
            groups[0] = (key, groups[0][1])
        for g in groups:
            if g[0] == key:
                g[1].append(c)
                break
        else:
            groups.append((key, [c]))
    review = any(c.review for c in cands)
    base: dict[str, Any] = dict(key=term.key, origin=Origin.RULES, needs_review=review)
    if len(groups) >= 2:
        shown = [Candidate(value=g[1][0].value, sources=_sources(g[1])) for g in groups]
        sources = _sources(concrete)
        return ProposedTerm(**base, value=None, raw=sources[0].quote, state=TermState.CONTRADICTED, sources=sources, candidates=shown,
                            confidence="low", unclear_reason=None, readings=[])
    if groups:
        group = groups[0][1]
        sources = _sources([*group, *vague])
        return ProposedTerm(**base, value=group[0].value, raw=sources[0].quote, state=TermState.STATED, sources=sources,
                            candidates=[Candidate(value=group[0].value, sources=_sources(group))], confidence="high",
                            unclear_reason=None, readings=[])
    if vague:
        sources = _sources(vague)
        return ProposedTerm(**base, value=None, raw=sources[0].quote, state=TermState.UNCLEAR, sources=sources, candidates=[],
                            confidence="low", unclear_reason=vague[0].reason, readings=next((c.readings for c in vague if c.readings), []))
    return ProposedTerm(**base, value=None, raw=None, state=TermState.MISSING, sources=[], candidates=[], confidence="low",
                        unclear_reason=None, readings=[])


def _signature(scan: _Scan, seg: tuple[int, int], amounts: list[AmountMatch], percents: list[Any]) -> tuple[Any, ...]:
    """The numbers in a sentence: two penalty sentences conflict only when their numbers differ."""
    def inside(item: Any) -> bool:
        return scan.segment(scan.sentences, item.start) == seg

    return tuple(sorted([a.paise for a in amounts if inside(a) and a.paise] + [p.basis_points for p in percents if inside(p)]))


def _total_paise(price: ProposedTerm, quantity: ProposedTerm | None) -> int | None:
    if price.state != TermState.STATED or not isinstance(price.value, MoneyValue):
        return None
    if price.value.per == "total":
        return int(price.value.paise)
    if price.value.per == "item" and quantity and quantity.state == TermState.STATED and isinstance(quantity.value, QuantityValue):
        return int(price.value.paise) * quantity.value.amount
    return None


def extract_terms(
    messages: Sequence[Message],
    playbook: Playbook,
    *,
    me_id: str,
    counterparty_id: str,
    date_order: str | None,
    eligible_ids: set[str] | None = None,
    reference_date: date | None = None,
) -> list[ProposedTerm]:
    """One ProposedTerm per playbook term, in playbook order. Sources are eligible messages only."""
    parties = {me_id, counterparty_id}
    msgs = [
        m
        for m in sorted(messages, key=lambda m: m.seq)
        if not m.is_system and m.sender_id in parties and (eligible_ids is None or m.id in eligible_ids) and not is_injection(m.text)
    ]
    terms = playbook.terms
    qty_terms = [t for t in terms if t.type == "quantity" and "quantities" in t.parsers]
    scope_term = next((t for t in terms if t.type == "text" and "quantities" in t.parsers), None)
    price_term = next((t for t in terms if t.type == "money" and "amounts" in t.parsers and "payment" not in t.parsers), None)
    pay_terms = [t for t in terms if t.type == "money" and "payment" in t.parsers]
    date_terms = [t for t in terms if t.type == "date" and "dates" in t.parsers]
    penalty_term = next((t for t in terms if "penalty" in t.parsers), None)
    text_terms = [t for t in terms if t.type in ("text", "enum") and not {"quantities", "penalty"} & set(t.parsers)]
    cue = {t.key: _cue_re([*t.cues["en"], *t.cues.get("hi", [])]) for t in terms}
    units = [w for t in qty_terms for w in t.cues["en"] + t.cues["hi"]]
    paid_re = _cue_re(_PAID_WORDS)
    pay_re = _cue_re([w for t in pay_terms for w in t.cues["en"] + t.cues["hi"]] if pay_terms else _FALLBACK_PAYMENT_WORDS)
    pen_re = cue[penalty_term.key] if penalty_term else _cue_re(_FALLBACK_PENALTY_WORDS)
    unit_names = {t.key: {w.lower() for w in t.cues["en"] + t.cues["hi"]} for t in qty_terms}

    cands: dict[str, list[_Cand]] = {t.key: [] for t in terms}
    paid: list[_Cand] = []

    for msg in msgs:
        scan = _Scan.of(msg)
        ref = reference_date or datetime.fromisoformat(msg.ts).date()
        amounts = parse_amounts(msg.text, units=units)
        quantities = parse_quantities(msg.text, units=units)
        dates = parse_dates(msg.text, reference=ref, date_order=date_order)
        percents = parse_percentages(msg.text)
        phrases = parse_payment_phrases(msg.text)
        penalties = parse_penalty_phrases(msg.text)

        def clause_text(item: Any) -> str:
            return scan.text(scan.segment(scan.clauses, item.start))

        def in_penalty(a: AmountMatch) -> bool:
            return a.period is not None or bool(pen_re and pen_re.search(clause_text(a)))

        # quantities and the unit noun
        for q in quantities:
            owner = next((t for t in qty_terms if q.unit and q.unit in unit_names[t.key]), qty_terms[0] if qty_terms and q.unit is None else None)
            if qty_terms and owner is None:
                continue
            src = scan.source(q.start, q.end)
            if owner:
                if q.vague or q.amount == 0:
                    cands[owner.key].append(_Cand(None, [src], reason=_reason(playbook, "vague_qty")))
                else:
                    cands[owner.key].append(_Cand(QuantityValue(amount=q.amount or 0, unit=q.unit), [src]))
            if scope_term and q.unit:
                cands[scope_term.key].append(_Cand(TextValue(text=q.unit), [src], key="generic" if q.unit in _GENERIC_UNITS else None))

        # amounts that are not payments become the price
        for a in amounts:
            ctext = clause_text(a)
            if in_penalty(a) or (pay_re and pay_re.search(ctext)):
                continue
            src = scan.source(a.start, a.end)
            if a.cue and paid_re and paid_re.search(a.cue) and pay_terms:
                paid.append(_Cand(PaymentValue(paise=str(a.paise), when="paid"), [src], review=a.currency != "INR"))
            elif price_term:
                review = a.currency != "INR"
                if a.approximate or a.paise is None:
                    cands[price_term.key].append(_Cand(None, [src], reason=_reason(playbook, "approx_amount"), review=review))
                else:
                    cands[price_term.key].append(
                        _Cand(MoneyValue(paise=str(a.paise), per=a.per), [src], review=review, kind="total" if a.per == "total" else "unit")
                    )

        # payment terms own the clauses that contain their cue words
        for seg in scan.clauses:
            ctext = scan.text(seg)

            def here(item: Any, seg: tuple[int, int] = seg) -> bool:
                return scan.segment(scan.clauses, item.start) == seg

            term = next((t for t in pay_terms if cue[t.key] and cue[t.key].search(ctext)), None)
            if not term:
                continue
            ams = [a for a in amounts if here(a) and not in_penalty(a)]
            pcts = [p for p in percents if here(p)] if "percent" in term.parsers else []
            phs = [p for p in phrases if here(p) and p.kind not in ("advance", "instalments")]
            dts = [d for d in dates if here(d)] if "dates" in term.parsers else []
            used: list[Any] = [*ams[:1], *pcts[:1], *phs, *dts]
            if not used:
                continue
            amount = ams[0] if ams else None
            when, days, on_date, reason, readings = None, None, None, None, []
            for p in phs:
                if p.kind == "later":
                    reason = "vague_pay"
                elif p.kind == "net_days":
                    when, days = "after_delivery", p.days
                else:
                    when = p.kind
            for d in dts:
                if d.kind == "absolute" and d.value:
                    when, on_date = when or "on_date", d.value.isoformat()
                elif d.rule_id:
                    reason, readings = reason or d.rule_id, [DateValue(date=r.isoformat()) for r in d.readings]
            if amount and (amount.approximate or amount.paise is None):
                reason = reason or "approx_amount"
            if when is None and paid_re and paid_re.search(ctext):
                when = "paid"
            src = scan.source(min(u.start for u in used), max(u.end for u in used))
            review = bool(amount and amount.currency != "INR")
            if reason:
                cands[term.key].append(_Cand(None, [src], reason=_reason(playbook, reason), review=review, readings=readings))
            else:
                value = PaymentValue(paise=str(amount.paise) if amount else None, when=when, days=days, date=on_date if when == "on_date" else None)
                cands[term.key].append(_Cand(value, [src], review=review, pct_bp=None if amount or not pcts else pcts[0].basis_points))

        # dates belong to the date term whose cue words the message contains, outside payment and penalty clauses
        for d in dates:
            ctext = clause_text(d)
            if (pay_re and pay_re.search(ctext)) or (pen_re and pen_re.search(ctext)):
                continue
            owner = next((t for t in date_terms if cue[t.key] and cue[t.key].search(scan.nz.text)), None)
            if not owner:
                continue
            src = scan.source(d.start, d.end)
            if d.kind == "absolute" and d.value:
                cands[owner.key].append(_Cand(DateValue(date=d.value.isoformat()), [src]))
            else:
                readings = [DateValue(date=r.isoformat()) for r in d.readings]
                cands[owner.key].append(_Cand(None, [src], reason=_reason(playbook, d.rule_id or "rel_date"), readings=readings))

        # the sentence that holds a penalty phrase
        if penalty_term:
            for seg in dict.fromkeys(scan.segment(scan.sentences, p.start) for p in penalties):
                src = scan.segment_source(seg)
                cands[penalty_term.key].append(_Cand(TextValue(text=src.quote), [src], key=_signature(scan, seg, amounts, percents)))

        # other text, enum and counted terms: sentences with the term's cue words, and the playbook's own patterns
        for term in [*text_terms, *qty_terms]:
            if not cue[term.key]:
                continue
            rules = [r for i in term.ambiguity if (r := playbook.rule(i)) and r.id not in _BUILTIN_RULES and r.patterns]
            for seg in scan.sentences:
                stext = scan.text(seg)
                if not cue[term.key].search(stext):
                    continue
                hit = next((r for r in rules if (rx := _cue_re(r.patterns)) and rx.search(stext)), None)
                if hit:
                    cands[term.key].append(_Cand(None, [scan.segment_source(seg)], reason=hit.id))
                elif term.type != "quantity":
                    src = scan.segment_source(seg)
                    cands[term.key].append(_Cand(TextValue(text=src.quote), [src], key=_signature(scan, seg, amounts, percents)))

    return _finish(playbook, cands, paid, pay_terms, price_term, qty_terms, scope_term, me_id, counterparty_id)


def _finish(
    playbook: Playbook,
    cands: dict[str, list[_Cand]],
    paid: list[_Cand],
    pay_terms: list[Term],
    price_term: Term | None,
    qty_terms: list[Term],
    scope_term: Term | None,
    me_id: str,
    counterparty_id: str,
) -> list[ProposedTerm]:
    """Resolve each term's candidates: quantity and price first, then payments that need the total."""
    out: dict[str, ProposedTerm] = {}
    for t in qty_terms:
        out[t.key] = _resolve(t, cands[t.key])
    quantity = out[qty_terms[0].key] if qty_terms else None
    if scope_term:
        specific = [c for c in cands[scope_term.key] if c.key != "generic"]
        out[scope_term.key] = _resolve(scope_term, specific or cands[scope_term.key])
    if price_term:
        out[price_term.key] = _resolve(price_term, _price_candidates(cands[price_term.key], quantity))
    total = _total_paise(out[price_term.key], quantity) if price_term else None
    for t in pay_terms:
        pool = cands[t.key]
        for c in pool:
            if c.pct_bp is not None:
                if total is None:
                    c.value, c.reason = None, _reason(playbook, "half_adv")
                else:
                    share = (Decimal(total) * c.pct_bp / 10000).quantize(Decimal(1), ROUND_HALF_UP)
                    c.value = c.value.model_copy(update={"paise": str(int(share))})
        pool = _merge_payments(pool)
        if t is pay_terms[0]:
            concrete = [c for c in pool if c.value is not None and c.reason is None]
            for p in paid:
                match = next((c for c in concrete if c.value.paise == p.value.paise), None)
                if match:
                    match.sources += p.sources
                    match.value = match.value.model_copy(update={"when": match.value.when or "paid"})
                elif not concrete:
                    pool.append(p)
                    concrete.append(p)
        out[t.key] = _resolve(t, pool)
    result: list[ProposedTerm] = []
    for t in playbook.terms:
        if t.key in out:
            result.append(out[t.key])
        elif t.type == "party":
            result.append(
                ProposedTerm(key=t.key, value=PartyValue(names=[me_id, counterparty_id]), raw=None, state=TermState.STATED, sources=[],
                             candidates=[], origin=Origin.RULES, confidence="high", needs_review=False, unclear_reason=None, readings=[])
            )
        else:
            result.append(_resolve(t, cands[t.key]))
    return result


def _price_candidates(cands: list[_Cand], quantity: ProposedTerm | None) -> list[_Cand]:
    """A total that equals quantity × unit price is a consistency check, not a second price."""
    units = [c for c in cands if c.kind == "unit"]
    totals = [c for c in cands if c.kind == "total"]
    vague = [c for c in cands if c.value is None]
    if not units:
        return totals + vague
    keep = list(units)
    prices = {c.value.paise for c in units}
    count = quantity.value.amount if quantity and quantity.state == TermState.STATED and isinstance(quantity.value, QuantityValue) else None
    if len(prices) == 1:
        for t in totals:
            if count is not None and int(t.value.paise) != count * int(next(iter(prices))):
                keep.append(t)
            else:
                units[0].sources += t.sources
    return keep + vague
