"""Phase 2: preview (FR-IMP-009), parties (FR-IMP-004) and which-one-is-you (FR-IMP-005)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from packages.contracts import Message, MessageOrigin
from packages.ingest.commit import SelectionError, prepare_commit
from packages.ingest.preview import build_preview
from packages.ingest.whatsapp import parse_export

MB = 1024 * 1024
IST = timezone(timedelta(hours=5, minutes=30))


def test_preview_counts_and_digest(chat_bytes):
    raw = chat_bytes("ambiguous.txt")
    p = build_preview(raw, "WhatsApp Chat - Raju.txt", max_bytes=MB)
    assert p.file_name == "WhatsApp Chat - Raju.txt"
    assert p.message_count == 5
    assert p.media_count == 0
    assert p.participants == ["Raju", "Meena"]
    assert p.date_range == (datetime(2026, 10, 12, 10, 2, tzinfo=IST), datetime(2026, 10, 13, 9, 15, tzinfo=IST))
    assert p.date_order == "DMY"
    assert p.needs_date_order_choice is False
    assert p.format_problem is False
    assert p.export_digest == hashlib.sha256(raw).hexdigest()  # raw bytes, no normalisation (INTEGRITY_SPEC 4.1)


def test_preview_counts_media_separately():
    data = b"14/10/26, 09:00 - Raju: <Media omitted>\n14/10/26, 09:01 - Meena: ok\n14/10/26, 09:02 - Meena: This message was deleted\n"
    p = build_preview(data, "chat.txt", max_bytes=MB)
    assert p.message_count == 1
    assert p.media_count == 1


def test_preview_creates_nothing_and_is_repeatable(chat_bytes):
    raw = chat_bytes("ambiguous.txt")
    assert build_preview(raw, "a.txt", max_bytes=MB) == build_preview(raw, "a.txt", max_bytes=MB)


def test_commit_produces_contract_messages(chat_bytes):
    r = parse_export(chat_bytes("ambiguous.txt"))
    d = prepare_commit(r, me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT, deal_id="d1")
    assert all(isinstance(m, Message) for m in d.messages)
    assert [m.seq for m in d.messages] == [1, 2, 3, 4, 5]
    assert all(m.deal_id == "d1" for m in d.messages)
    assert d.messages[0].ts == "2026-10-12T10:02:00+05:30"
    ids = [m.id for m in d.messages]
    assert len(set(ids)) == 5 and all(uuid.UUID(i) for i in ids)
    me = next(p for p in d.participants if p.is_me)
    assert me.display_name == "Raju" and d.me_id == me.id
    other = next(p for p in d.participants if p.id == d.counterparty_id)
    assert other.display_name == "Meena" and other.role == "party"


@pytest.mark.parametrize(
    "me,cp",
    [(None, "Meena"), ("Raju", None), ("Raju", "Raju"), ("Nobody", "Meena"), ("Raju", "Ghost")],
)
def test_invalid_party_selection_refused(chat_bytes, me, cp):
    r = parse_export(chat_bytes("ambiguous.txt"))
    with pytest.raises(SelectionError):
        prepare_commit(r, me=me, counterparty=cp, playbook_key="supply_order", origin=MessageOrigin.EXPORT)


def test_commit_refused_while_date_order_unknown():
    r = parse_export(b"01/02/26, 09:00 - Raju: a\n03/04/26, 09:00 - Meena: b\n")
    with pytest.raises(SelectionError):
        prepare_commit(r, me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)


def test_group_chat_context_sender_not_eligible(chat_bytes):
    r = parse_export(chat_bytes("group.txt"))
    assert r.participants == ["Raju", "Meena", "Ravi"]
    d = prepare_commit(r, me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT, deal_id="d1")
    ravi = next(p for p in d.participants if p.display_name == "Ravi")
    assert ravi.role == "context" and not ravi.is_me
    ravi_msgs = [m for m in d.messages if m.sender_id == ravi.id]
    assert ravi_msgs, "context messages are kept"
    assert not any(m.id in d.eligible_message_ids for m in ravi_msgs)


def test_system_media_and_deleted_entries_never_eligible():
    data = (
        b"14/10/26, 09:00 - Raju added Meena\n"
        b"14/10/26, 09:01 - Raju: <Media omitted>\n"
        b"14/10/26, 09:02 - Meena: This message was deleted\n"
        b"14/10/26, 09:03 - Raju: 100 shirts\n"
        b"15/10/26, 09:04 - Meena: ok\n"
    )
    d = prepare_commit(parse_export(data), me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT, deal_id="d1")
    eligible = [m.text for m in d.messages if m.id in d.eligible_message_ids]
    assert eligible == ["100 shirts", "ok"]
    system = [m for m in d.messages if m.is_system]
    assert len(system) == 1 and system[0].sender_id is None


def test_preview_of_unknown_date_order_has_no_date_range():
    data = b"01/02/26, 09:00 - Raju: a\n03/04/26, 09:00 - Meena: b\n"
    p = build_preview(data, "c.txt", max_bytes=MB)
    assert p.needs_date_order_choice and p.date_range == (None, None)
    again = build_preview(data, "c.txt", max_bytes=MB, date_order="DMY")
    assert not again.needs_date_order_choice and again.date_range[0].month == 2


def test_commit_without_deal_id_creates_a_uuid(chat_bytes):
    r = parse_export(chat_bytes("ambiguous.txt"))
    d = prepare_commit(r, me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)
    assert uuid.UUID(d.deal_id) and all(m.deal_id == d.deal_id for m in d.messages)
    assert d.playbook_key == "supply_order" and d.origin == MessageOrigin.EXPORT


def test_commit_timestamps_keep_the_offset_and_twelve_hour_times(chat_bytes):
    r = parse_export(chat_bytes("android_12h.txt"))
    d = prepare_commit(r, me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT, deal_id="d1")
    assert [m.ts for m in d.messages] == [
        "2026-10-14T09:00:00+05:30",
        "2026-10-14T21:05:00+05:30",
        "2026-10-14T00:10:00+05:30",
        "2026-10-14T12:10:00+05:30",
    ]


def test_commit_writes_nothing(chat_bytes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = parse_export(chat_bytes("group.txt"))
    prepare_commit(r, me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)
    assert list(tmp_path.iterdir()) == []
