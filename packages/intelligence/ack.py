"""Acknowledgement detection (FR-FLG-005): did the other side reply to a term?"""

from __future__ import annotations

import re
from collections.abc import Sequence

from packages.contracts import Message, PartyValue, ProposedTerm

from .rules import parse_amounts

_AGREE = re.compile(r"(?<!\w)(?:ok|okay|done|yes|haan|ha|theek hai|thik hai|agreed|confirmed|sure)(?!\w)|👍", re.IGNORECASE)
_NEGATION = re.compile(r"(?<!\w)(?:no|not|nahi|nahin|nope|never|don't|dont|can't|cannot)(?!\w)", re.IGNORECASE)


def agrees(text: str) -> bool:
    return bool(_AGREE.search(text)) and not _NEGATION.search(text)


def _amount(term: ProposedTerm) -> int | None:
    paise = getattr(term.value, "paise", None)
    return int(paise) if paise else None


def acknowledged_keys(
    terms: Sequence[ProposedTerm], messages: Sequence[Message], *, me_id: str, counterparty_id: str, window: int = 5
) -> set[str]:
    """Keys of terms with a source followed, within ``window`` messages, by the other party agreeing
    or by a payment of the same amount. A party-term is acknowledged once both people have written."""
    chat = sorted((m for m in messages if not m.is_system and m.sender_id in (me_id, counterparty_id)), key=lambda m: m.seq)
    position = {m.id: i for i, m in enumerate(chat)}
    acked: set[str] = set()
    for term in terms:
        if isinstance(term.value, PartyValue) and {m.sender_id for m in chat} == {me_id, counterparty_id}:
            acked.add(term.key)
        amount = _amount(term)
        for source in term.sources:
            i = position.get(source.message_id)
            if i is None:
                continue
            for later in chat[i + 1 : i + 1 + window]:
                if later.sender_id != chat[i].sender_id and (
                    agrees(later.text) or (amount is not None and any(a.paise == amount for a in parse_amounts(later.text)))
                ):
                    acked.add(term.key)
    return acked
