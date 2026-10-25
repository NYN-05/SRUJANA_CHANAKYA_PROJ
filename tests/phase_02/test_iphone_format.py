"""Phase 2: iPhone export parsing (FR-IMP-001)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.ingest.whatsapp import parse_export

IST = timezone(timedelta(hours=5, minutes=30))


def parse(text: str, **kw):
    return parse_export(text.encode("utf-8"), **kw)


def test_clean_fixture_has_seconds(chat_bytes):
    r = parse_export(chat_bytes("clean.txt"))
    assert r.format == "iphone"
    assert r.date_order == "DMY"
    assert r.participants == ["Anita", "Rohit"]
    assert len(r.messages) == 6
    assert r.messages[1].ts == datetime(2026, 10, 20, 9, 5, 12, tzinfo=IST)


def test_iphone_header_from_prd_example():
    r = parse("[24/10/2026, 11:42:10] Raju: ok\n")
    assert r.messages[0].ts == datetime(2026, 10, 24, 11, 42, 10, tzinfo=IST)


def test_left_to_right_mark_is_ignored():
    r = parse("‎[24/10/2026, 11:42:10] Raju: ‎image omitted\n[24/10/2026, 11:43:00] Meena: ok\n")
    assert r.messages[0].kind == "media"
    assert r.messages[0].sender == "Raju"
    assert r.participants == ["Raju", "Meena"]


def test_attached_audio_name():
    r = parse("[24/10/2026, 11:42:10] Raju: ‎<attached: 00000012-AUDIO-2026-10-24-11-42-10.opus>\n")
    assert r.messages[0].kind == "media"
    assert r.messages[0].attachment_name == "00000012-AUDIO-2026-10-24-11-42-10.opus"


def test_twelve_hour_iphone():
    r = parse("[24/10/26, 1:05:00 PM] Raju: a\n[24/10/26, 12:30:00 AM] Meena: b\n")
    assert [(m.ts.hour, m.ts.minute) for m in r.messages] == [(13, 5), (0, 30)]


def test_multiline_iphone():
    r = parse("[24/10/2026, 11:42:10] Raju: one\ntwo\n[24/10/2026, 11:43:00] Meena: ok\n")
    assert r.messages[0].text == "one\ntwo"


def test_bom_and_crlf(chat_bytes):
    raw = chat_bytes("clean.txt").replace(b"\n", b"\r\n")
    r1 = parse_export(b"\xef\xbb\xbf" + raw)
    r2 = parse_export(chat_bytes("clean.txt"))
    assert [(m.sender, m.text, m.ts) for m in r1.messages] == [(m.sender, m.text, m.ts) for m in r2.messages]


def test_iphone_notice_carries_the_chat_name_as_sender():
    notice = "Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them."
    r = parse(f"[24/10/2026, 11:40:00] Meena: ‎{notice}\n[24/10/2026, 11:42:10] Raju: ok\n")
    assert r.messages[0].kind == "system" and r.messages[0].sender is None
    assert r.participants == ["Raju"]


def test_iphone_deleted_message():
    r = parse("[24/10/2026, 11:42:10] Raju: ‎This message was deleted\n")
    assert r.messages[0].kind == "deleted"
