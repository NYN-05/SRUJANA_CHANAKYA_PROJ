"""Phase 2: pasted text equals the same text as a file (FR-IMP-006)."""

from __future__ import annotations

from packages.contracts import MessageOrigin
from packages.ingest.commit import prepare_commit
from packages.ingest.whatsapp import parse_export


def fields(draft):
    return [(m.seq, m.sender_id, m.ts, m.text, m.is_system) for m in draft.messages]


def test_paste_gives_identical_messages(chat_bytes):
    raw = chat_bytes("ambiguous.txt")
    from_file = parse_export(raw)
    from_paste = parse_export(raw.decode("utf-8"))  # str input = pasted text
    kw = dict(me="Raju", counterparty="Meena", playbook_key="supply_order", deal_id="d1")
    a = prepare_commit(from_file, origin=MessageOrigin.EXPORT, **kw)
    b = prepare_commit(from_paste, origin=MessageOrigin.PASTE, **kw)
    assert fields(a) == fields(b)
    assert {m.origin for m in a.messages} == {MessageOrigin.EXPORT}
    assert {m.origin for m in b.messages} == {MessageOrigin.PASTE}


def test_pasted_text_with_windows_line_endings(chat_bytes):
    raw = chat_bytes("ambiguous.txt").decode("utf-8")
    assert [m.text for m in parse_export(raw.replace("\n", "\r\n")).messages] == [
        m.text for m in parse_export(raw).messages
    ]
