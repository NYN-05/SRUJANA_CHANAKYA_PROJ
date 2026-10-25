"""Phase 2: malformed and partial files never fail silently (FR-IMP-003)."""

from __future__ import annotations

import os

import pytest

from packages.ingest.errors import ImportRefused
from packages.ingest.preview import build_preview
from packages.ingest.whatsapp import parse_export

MB = 1024 * 1024


def test_random_bytes_refused():
    data = os.urandom(4096)
    with pytest.raises(ImportRefused) as err:
        build_preview(data, "x.txt", max_bytes=MB)
    assert err.value.code in {"binary", "not_whatsapp"}


def test_empty_file_refused():
    with pytest.raises(ImportRefused) as err:
        build_preview(b"", "x.txt", max_bytes=MB)
    assert err.value.code == "empty"


def test_whitespace_only_file_refused():
    with pytest.raises(ImportRefused) as err:
        build_preview(b"\n \n\t\n", "x.txt", max_bytes=MB)
    assert err.value.code == "empty"


def test_nul_bytes_refused_as_binary():
    with pytest.raises(ImportRefused) as err:
        build_preview(b"14/10/26, 09:00 - Raju: hi\x00\x00\x00\x00" * 50, "x.txt", max_bytes=MB)
    assert err.value.code == "binary"


def test_too_large_refused():
    with pytest.raises(ImportRefused) as err:
        build_preview(b"a" * (MB + 1), "x.txt", max_bytes=MB)
    assert err.value.code == "too_large"


def test_text_that_is_not_a_chat_refused():
    with pytest.raises(ImportRefused) as err:
        build_preview(b"Dear sir,\nPlease find attached the invoice.\nRegards\n", "letter.txt", max_bytes=MB)
    assert err.value.code == "not_whatsapp"


def test_thirty_percent_unparsed_shows_format_problem():
    good = [f"14/10/26, 09:{i:02d} - Raju: message {i}" for i in range(7)]
    # three garbage lines that are not continuations: placed before the first header
    bad = ["@@@ garbage one", "### garbage two", "%%% garbage three"]
    data = "\n".join(bad + good).encode()
    p = build_preview(data, "chat.txt", max_bytes=MB)
    assert p.format_problem is True
    assert [ln for ln, _ in p.first_unparsed_lines] == [1, 2, 3]


def test_above_eighty_percent_has_no_banner():
    good = [f"14/10/26, 09:{i:02d} - Raju: message {i}" for i in range(9)]
    data = "\n".join(["@@@ preamble"] + good).encode()
    p = build_preview(data, "chat.txt", max_bytes=MB)
    assert p.format_problem is False


def test_first_unparsed_lines_capped_at_five():
    bad = [f"junk {i}" for i in range(20)]
    good = [f"14/10/26, 09:{i:02d} - Raju: m{i}" for i in range(5)]
    p = build_preview("\n".join(bad + good).encode(), "chat.txt", max_bytes=MB)
    assert len(p.first_unparsed_lines) == 5


def test_only_system_lines_has_no_participants():
    data = b"14/10/26, 09:00 - Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.\n"
    r = parse_export(data)
    assert r.participants == []
    assert r.messages[0].kind == "system"


def test_invalid_utf8_sequences_are_tolerated_when_rare():
    data = "14/10/26, 09:00 - Raju: price 480\n".encode() + b"14/10/26, 09:01 - Meena: ok \xff\n"
    r = parse_export(data)
    assert len(r.messages) == 2
    assert "invalid_utf8" in r.warnings


def test_many_invalid_utf8_sequences_refused_as_binary():
    data = "14/10/26, 09:00 - Raju: price 480\n".encode() + b"\xff\xfe\xfd" * 20
    with pytest.raises(ImportRefused) as err:
        parse_export(data)
    assert err.value.code == "binary"


def test_pasted_text_with_nul_refused():
    with pytest.raises(ImportRefused) as err:
        parse_export("14/10/26, 09:00 - Raju: hi\x00")
    assert err.value.code == "binary"


def test_size_cap_is_checked_on_raw_bytes_before_parsing():
    with pytest.raises(ImportRefused) as err:
        build_preview(b"\x00" * (MB + 1), "x.txt", max_bytes=MB)
    assert err.value.code == "too_large"


def test_unknown_refusal_code_is_a_programming_error():
    with pytest.raises(ValueError):
        ImportRefused("oops")


def test_parse_ratio_reported():
    r = parse_export(b"junk\n14/10/26, 09:00 - Raju: a\n14/10/26, 09:01 - Meena: b\n14/10/26, 09:02 - Meena: c\n")
    assert r.parse_ratio == 0.75 and r.unparsed_lines == [(1, "junk")]
