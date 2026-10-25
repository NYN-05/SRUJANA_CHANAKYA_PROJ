"""Turn an accepted preview into contract messages (FR-IMP-004, FR-IMP-005). Pure: the vault write is Phase 5."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from packages.contracts import Message, MessageOrigin

from .whatsapp import ParseResult


class SelectionError(ValueError):
    """The party choice is missing or invalid, or the date order is still unknown."""


@dataclass(frozen=True)
class Participant:
    id: str  # the display name as exported; unique within one chat
    display_name: str
    role: Literal["party", "context"]
    is_me: bool


@dataclass(frozen=True)
class DealDraft:
    deal_id: str
    playbook_key: str
    origin: MessageOrigin
    participants: list[Participant]
    messages: list[Message]
    eligible_message_ids: set[str]  # text entries of the two parties only: the term sources
    me_id: str
    counterparty_id: str


def prepare_commit(
    parse_result: ParseResult,
    *,
    me: str | None,
    counterparty: str | None,
    playbook_key: str,
    origin: MessageOrigin,
    deal_id: str | None = None,
) -> DealDraft:
    people = parse_result.participants
    if not me or not counterparty:
        raise SelectionError("choose which participant is you and who the other party is")
    if me not in people or counterparty not in people:
        raise SelectionError("both parties must be participants of the chat")
    if me == counterparty:
        raise SelectionError("you and the other party must be different participants")
    if parse_result.needs_date_order_choice or any(m.ts is None for m in parse_result.messages):
        raise SelectionError("choose the date order (day first or month first) before continuing")

    deal_id = deal_id or str(uuid.uuid4())
    parties = {me, counterparty}
    messages, eligible = [], set()
    for entry in parse_result.messages:
        assert entry.ts is not None  # checked above
        msg = Message(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            seq=entry.seq,
            sender_id=entry.sender,
            ts=entry.ts.isoformat(timespec="seconds"),  # YYYY-MM-DDTHH:MM:SS+HH:MM, never Z
            text=entry.text,
            attachment_hash=None,  # media bytes are hashed when the vault stores them (Phase 5)
            is_system=entry.kind == "system",
            origin=origin,
        )
        messages.append(msg)
        if entry.kind == "text" and entry.sender in parties:
            eligible.add(msg.id)
    participants = [
        Participant(id=name, display_name=name, role="party" if name in parties else "context", is_me=name == me)
        for name in people
    ]
    return DealDraft(deal_id, playbook_key, origin, participants, messages, eligible, me, counterparty)
