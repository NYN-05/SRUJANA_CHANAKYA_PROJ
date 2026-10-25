"""Phase 2: zip exports with media (FR-IMP-002 archive part; THREAT_MODEL T13)."""

from __future__ import annotations

import io
import zipfile

import pytest

from packages.ingest.archive import read_export_zip
from packages.ingest.errors import ImportRefused

MB = 1024 * 1024
CHAT = (
    "14/10/26, 09:00 - Raju: PTT-20261014-WA0001.opus (file attached)\n"
    "14/10/26, 09:01 - Meena: IMG-20261014-WA0002.jpg (file attached)\n"
    "14/10/26, 09:02 - Raju: ok\n"
).encode()


def make_zip(entries: dict[str, bytes], compression=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def read(data: bytes, **kw):
    kw.setdefault("max_total_bytes", 50 * MB)
    return read_export_zip(data, **kw)


def test_chat_and_media_found():
    z = make_zip({"WhatsApp Chat with Meena.txt": CHAT, "PTT-20261014-WA0001.opus": b"OggS-audio", "IMG-20261014-WA0002.jpg": b"\xff\xd8jpeg"})
    out = read(z)
    assert out.chat_name == "WhatsApp Chat with Meena.txt"
    assert out.chat_text == CHAT
    assert set(out.media) == {"PTT-20261014-WA0001.opus", "IMG-20261014-WA0002.jpg"}
    assert out.rejected == []


def test_iphone_chat_file_name():
    out = read(make_zip({"_chat.txt": CHAT}))
    assert out.chat_name == "_chat.txt"


@pytest.mark.parametrize("evil", ["../../x", "/etc/passwd", "C:/Windows/x.dll", "..\\..\\x", "media/../../x"])
def test_unsafe_paths_rejected_and_import_continues(evil):
    out = read(make_zip({"_chat.txt": CHAT, evil: b"payload"}))
    assert out.chat_text == CHAT
    assert evil not in out.media and "x" not in out.media
    # zipfile turns a backslash into "/" in entry names on Windows, so accept either spelling
    names = {evil, evil.replace("\\", "/")}
    assert any(name in names and reason == "unsafe_path" for name, reason in out.rejected)


def test_no_chat_file_refused():
    with pytest.raises(ImportRefused) as err:
        read(make_zip({"photo.jpg": b"\xff\xd8"}))
    assert err.value.code == "no_chat_file"


def test_not_a_zip_refused():
    with pytest.raises(ImportRefused) as err:
        read(b"PK\x03\x04 this is not really a zip")
    assert err.value.code == "bad_zip"


def test_zip_bomb_ratio_refused():
    bomb = make_zip({"_chat.txt": CHAT, "big.bin": b"\x00" * (20 * MB)})
    with pytest.raises(ImportRefused) as err:
        read(bomb, max_ratio=100)
    assert err.value.code == "zip_limits"


def test_total_size_cap_refused():
    data = make_zip({"_chat.txt": CHAT, "a.opus": bytes(range(256)) * 8192}, compression=zipfile.ZIP_STORED)
    with pytest.raises(ImportRefused) as err:
        read(data, max_total_bytes=MB)
    assert err.value.code == "zip_limits"


def test_entry_count_cap_refused():
    entries = {"_chat.txt": CHAT, **{f"f{i}.jpg": b"x" for i in range(30)}}
    with pytest.raises(ImportRefused) as err:
        read(make_zip(entries), max_entries=10)
    assert err.value.code == "zip_limits"


def test_duplicate_media_names_keep_first_and_warn():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("_chat.txt", CHAT)
        z.writestr("a.opus", b"first")
        z.writestr("a.opus", b"second")
    out = read(buf.getvalue())
    assert out.media["a.opus"] == b"first"
    assert any("duplicate" in w for w in out.warnings)


def test_unmatched_and_missing_media_listed():
    out = read(make_zip({"_chat.txt": CHAT, "PTT-20261014-WA0001.opus": b"a", "stray.pdf": b"%PDF"}))
    assert "stray.pdf" in out.unmatched_media
    assert "IMG-20261014-WA0002.jpg" in out.missing_media


def test_single_txt_with_another_name_is_the_chat():
    out = read(make_zip({"chat export.txt": CHAT}))
    assert out.chat_name == "chat export.txt"


def test_two_unnamed_txt_files_are_ambiguous():
    with pytest.raises(ImportRefused) as err:
        read(make_zip({"a.txt": CHAT, "b.txt": CHAT}))
    assert err.value.code == "no_chat_file"


def test_named_chat_wins_over_other_txt_files():
    out = read(make_zip({"notes.txt": b"x", "WhatsApp Chat with Meena.txt": CHAT}))
    assert out.chat_name == "WhatsApp Chat with Meena.txt"
    assert "notes.txt" in out.unmatched_media


def test_media_in_a_subfolder_is_matched_by_name():
    out = read(make_zip({"_chat.txt": CHAT, "Media/PTT-20261014-WA0001.opus": b"a"}))
    assert "PTT-20261014-WA0001.opus" in out.media
    assert "PTT-20261014-WA0001.opus" not in out.missing_media


def test_corrupt_entry_is_bad_zip():
    data = bytearray(make_zip({"_chat.txt": CHAT * 50}))
    start = data.index(b"_chat.txt") + len(b"_chat.txt")
    data[start + 5 : start + 40] = b"\x00" * 35  # damage the compressed stream
    with pytest.raises(ImportRefused) as err:
        read(bytes(data))
    assert err.value.code in {"bad_zip", "no_chat_file"}


def test_small_highly_compressible_chat_is_not_a_bomb():
    chat = b"14/10/26, 09:00 - Raju: ok\n" * 20_000  # about 540 KB of one repeated line
    out = read(make_zip({"_chat.txt": chat}), max_ratio=100)
    assert out.chat_text == chat


def test_nothing_is_extracted_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    read(make_zip({"_chat.txt": CHAT, "../../x": b"payload", "a.opus": b"a"}))
    assert list(tmp_path.iterdir()) == []
