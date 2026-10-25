"""Phase 2: Android export parsing (FR-IMP-001)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.ingest.whatsapp import parse_export

IST = timezone(timedelta(hours=5, minutes=30))


def parse(text: str, **kw):
    return parse_export(text.encode("utf-8"), **kw)


def texts(result):
    return [m.text for m in result.messages]


def test_ambiguous_fixture(chat_bytes):
    r = parse_export(chat_bytes("ambiguous.txt"))
    assert r.format == "android"
    assert r.date_order == "DMY"
    assert r.participants == ["Raju", "Meena"]
    assert [m.sender for m in r.messages] == ["Raju", "Meena", "Raju", "Meena", "Raju"]
    assert [m.seq for m in r.messages] == [1, 2, 3, 4, 5]
    assert r.messages[0].text == "200 shirts, 480 each ok?"
    assert r.messages[0].ts == datetime(2026, 10, 12, 10, 2, tzinfo=IST)
    assert r.messages[4].ts == datetime(2026, 10, 13, 9, 15, tzinfo=IST)
    assert all(m.kind == "text" for m in r.messages)
    assert r.unparsed_lines == []


def test_utc_offset_argument_is_applied(chat_bytes):
    r = parse_export(chat_bytes("ambiguous.txt"), utc_offset="+00:00")
    assert r.messages[0].ts.utcoffset() == timedelta(0)


def test_twelve_hour_clock(chat_bytes):
    r = parse_export(chat_bytes("android_12h.txt"))
    hours = [(m.ts.hour, m.ts.minute) for m in r.messages]
    assert hours == [(9, 0), (21, 5), (0, 10), (12, 10)]


def test_narrow_no_break_space_before_pm():
    r = parse("14/10/26, 9:05 pm - Meena: ok\n14/10/26, 9:06 PM - Raju: fine\n")
    assert [m.ts.hour for m in r.messages] == [21, 21]


def test_multi_line_message_joins_previous():
    r = parse("14/10/26, 10:00 - Raju: line one\nline two\n  line three\n14/10/26, 10:01 - Meena: ok\n")
    assert texts(r) == ["line one\nline two\n  line three", "ok"]


def test_body_line_that_starts_with_a_date_stays_in_message():
    body = "14/10/26, 10:00 - Raju: list:\n15/11/26 we deliver the first lot\n16/11 second lot\n"
    r = parse(body + "14/10/26, 10:05 - Meena: ok\n")
    assert len(r.messages) == 2
    assert "15/11/26 we deliver the first lot" in r.messages[0].text
    assert "16/11 second lot" in r.messages[0].text


def test_system_lines_are_kept_and_flagged(chat_bytes):
    r = parse_export(chat_bytes("contradictory.txt"))
    first = r.messages[0]
    assert first.kind == "system" and first.sender is None
    assert first.seq == 1  # I-10: system lines are numbered too
    assert "Patel" in r.participants and "Sai" in r.participants
    assert len(r.participants) == 2


@pytest.mark.parametrize(
    "line",
    [
        "Raju added Meena",
        "Raju created group \"Shirt order: winter\"",
        "Raju changed the subject to \"Order: shirts\"",
        "Meena left",
        "Raju removed Ravi",
        "Your security code with Meena changed. Tap to learn more.",
        "Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.",
        "Meena joined using this group's invite link",
        "Raju changed this group's icon",
    ],
)
def test_known_system_patterns_checked_before_sender_split(line):
    r = parse(f"14/10/26, 09:00 - {line}\n14/10/26, 09:01 - Raju: hi\n")
    assert r.messages[0].kind == "system"
    assert r.participants == ["Raju"]


@pytest.mark.parametrize("placeholder", ["<Media omitted>", "image omitted", "audio omitted", "document omitted"])
def test_media_placeholders(placeholder):
    r = parse(f"14/10/26, 09:00 - Raju: {placeholder}\n")
    assert r.messages[0].kind == "media"
    assert r.messages[0].sender == "Raju"


def test_attached_file_name_is_captured():
    r = parse("14/10/26, 09:00 - Raju: PTT-20261014-WA0001.opus (file attached)\n")
    assert r.messages[0].kind == "media"
    assert r.messages[0].attachment_name == "PTT-20261014-WA0001.opus"


@pytest.mark.parametrize("deleted", ["This message was deleted", "You deleted this message"])
def test_deleted_messages(deleted):
    r = parse(f"14/10/26, 09:00 - Raju: {deleted}\n")
    assert r.messages[0].kind == "deleted"


def test_sender_text_with_more_colons():
    r = parse("14/10/26, 09:00 - Raju: re: price: 480 each\n")
    assert r.messages[0].sender == "Raju"
    assert r.messages[0].text == "re: price: 480 each"


def test_emoji_devanagari_and_kannada_text():
    r = parse("14/10/26, 09:00 - Raju: ठीक है 👍 ಸರಿ\n14/10/26, 09:01 - मीना: ok\n")
    assert r.messages[0].text == "ठीक है 👍 ಸರಿ"
    assert r.participants == ["Raju", "मीना"]


def test_empty_text_after_header():
    r = parse("14/10/26, 09:00 - Raju: \n14/10/26, 09:01 - Meena: ok\n")
    assert texts(r) == ["", "ok"]


def test_trailing_blank_lines_ignored():
    r = parse("14/10/26, 09:00 - Raju: hi\n\n\n")
    assert texts(r) == ["hi"]


def test_line_numbers_recorded():
    r = parse("14/10/26, 09:00 - Raju: a\nmore\n14/10/26, 09:01 - Meena: b\n")
    assert [m.line_no for m in r.messages] == [1, 3]


def test_two_digit_year_is_this_century():
    r = parse("14/10/26, 09:00 - Raju: a\n")
    assert r.messages[0].ts.year == 2026


def test_message_saying_left_or_added_is_not_a_system_notice():
    r = parse("14/10/26, 09:00 - Ravi: left\n14/10/26, 09:01 - Raju: we added 20 more\n")
    assert [m.kind for m in r.messages] == ["text", "text"]
    assert r.participants == ["Ravi", "Raju"]


def test_impossible_header_inside_chat_is_unparsed_not_joined():
    r = parse("14/10/26, 09:00 - Raju: a\n31/02/26, 09:00 - Raju: b\n14/10/26, 09:02 - Meena: c\n")
    assert [m.text for m in r.messages] == ["a", "c"]
    assert r.unparsed_lines == [(2, "31/02/26, 09:00 - Raju: b")]


def test_invalid_time_is_not_a_header():
    r = parse("14/10/26, 09:00 - Raju: a\n14/10/26, 25:00 - Raju: b\n14/10/26, 13:00 pm - Raju: c\n")
    assert len(r.messages) == 1
    assert [n for n, _ in r.unparsed_lines] == [2, 3]


def test_sender_without_trailing_space_gives_empty_text():
    r = parse("14/10/26, 09:00 - Raju:\n14/10/26, 09:01 - Meena: ok\n")
    assert r.messages[0].sender == "Raju" and r.messages[0].text == ""


def test_media_with_caption_on_the_next_line():
    r = parse("14/10/26, 09:00 - Raju: IMG-20261014-WA0002.jpg (file attached)\nthis is the design\n")
    assert r.messages[0].kind == "media"
    assert r.messages[0].text.endswith("this is the design")


def test_invalid_utc_offset_is_a_value_error():
    with pytest.raises(ValueError):
        parse("14/10/26, 09:00 - Raju: a\n", utc_offset="IST")


def test_four_digit_year_on_android():
    r = parse("14/10/2026, 09:00 - Raju: a\n")
    assert r.messages[0].ts == datetime(2026, 10, 14, 9, 0, tzinfo=IST)
