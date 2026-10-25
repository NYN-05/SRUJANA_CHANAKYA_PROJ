"""Small builders shared by the phase tests.

They use only the public interfaces listed in PHASES.md Appendix A.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHATS = Path(__file__).resolve().parent / "fixtures" / "chats"
IST = timezone(timedelta(hours=5, minutes=30))
DEAL_ID = "00000000-0000-4000-8000-000000000001"


def ts(day: int, hour: int, minute: int, second: int = 0, month: int = 10, year: int = 2026) -> str:
    return datetime(year, month, day, hour, minute, second, tzinfo=IST).isoformat()


def make_messages(rows, deal_id: str = DEAL_ID):
    """rows: list of (sender_id, text) or (sender_id, text, ts_str). Returns contract Messages."""
    from packages.contracts import Message, MessageOrigin

    out = []
    base = datetime(2026, 10, 12, 10, 0, tzinfo=IST)
    for i, row in enumerate(rows, start=1):
        sender, text = row[0], row[1]
        stamp = row[2] if len(row) > 2 else (base + timedelta(minutes=i)).isoformat()
        out.append(
            Message(
                id=str(uuid.UUID(int=i)),
                deal_id=deal_id,
                seq=i,
                sender_id=sender,
                ts=stamp,
                text=text,
                attachment_hash=None,
                is_system=False,
                origin=MessageOrigin.EXPORT,
            )
        )
    return out


def sample_draft(name: str, me: str, counterparty: str, playbook_key: str = "supply_order", deal_id: str | None = None):
    """Parse a fixture chat and prepare a commit draft (no database). A fresh deal id each call by default."""
    from packages.contracts import MessageOrigin
    from packages.ingest.commit import prepare_commit
    from packages.ingest.whatsapp import parse_export

    result = parse_export((CHATS / name).read_bytes())
    return prepare_commit(
        result,
        me=me,
        counterparty=counterparty,
        playbook_key=playbook_key,
        origin=MessageOrigin.EXPORT,
        deal_id=deal_id or str(uuid.uuid4()),
    )


def terms_by_key(terms):
    return {t.key: t for t in terms}


def rules_terms(messages, playbook, me="Raju", counterparty="Meena", date_order="DMY"):
    from packages.intelligence.extract import extract_terms

    return terms_by_key(
        extract_terms(messages, playbook, me_id=me, counterparty_id=counterparty, date_order=date_order)
    )


def commit_sample(vault, name: str, me: str, counterparty: str, playbook_key: str = "supply_order", media=None):
    """Parse a fixture chat, commit it to the vault, save rules proposals. Returns (deal_id, draft)."""
    from packages.intelligence.extract import extract_terms
    from packages.intelligence.playbooks import load_playbook

    raw = (CHATS / name).read_bytes()
    draft = sample_draft(name, me, counterparty, playbook_key)
    deal_id = vault.commit_import(draft, export_bytes=raw, file_name=name, media=media or {})
    playbook = load_playbook(Path(__file__).resolve().parents[1] / "playbooks" / f"{playbook_key}.yaml")
    terms = extract_terms(
        vault.messages(deal_id),
        playbook,
        me_id=draft.me_id,
        counterparty_id=draft.counterparty_id,
        date_order="DMY",
        eligible_ids=draft.eligible_message_ids,
    )
    vault.save_proposals(deal_id, terms)
    return deal_id, draft


def confirm_clear_terms(vault, deal_id, keys=("parties", "scope", "quantity", "price", "advance")):
    for key in keys:
        vault.confirm_term(deal_id, key)


def chat_of(n: int) -> bytes:
    """A synthetic two-party Android chat with n messages."""
    lines = []
    for i in range(n):
        sender = "Raju" if i % 2 == 0 else "Meena"
        lines.append(f"{13 + (i // 1000):02d}/10/26, {9 + (i // 60) % 12:02d}:{i % 60:02d} - {sender}: message {i + 1}")
    return ("\n".join(lines) + "\n").encode()


# The Raju and Meena chat used across phases (same content as ambiguous.txt).
RAJU_MEENA = [
    ("Raju", "200 shirts, 480 each ok?"),
    ("Meena", "ok. delivery next week"),
    ("Raju", "advance half now"),
    ("Meena", "done sent 48000"),
    ("Raju", "received. will message when ready"),
]
