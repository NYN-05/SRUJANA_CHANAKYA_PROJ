"""Streaming reader for zipped exports with media (FR-IMP-002; THREAT_MODEL T13).

Caps entry count, total uncompressed bytes (counted while reading, not trusted from headers) and the
compression ratio. Unsafe entry paths are rejected and listed, and the import continues without them.
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .errors import ImportRefused
from .whatsapp import parse_export

CHUNK = 64 * 1024
RATIO_FLOOR = 1024 * 1024  # small entries (a short chat text) may legitimately compress very well
_DRIVE = re.compile(r"[A-Za-z]:")
_CHAT_NAME = re.compile(r"_chat\.txt|WhatsApp Chat.*\.txt", re.IGNORECASE)


@dataclass(frozen=True)
class ZipExport:
    chat_name: str
    chat_text: bytes
    media: dict[str, bytes]
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (entry name, reason)
    warnings: list[str] = field(default_factory=list)
    unmatched_media: list[str] = field(default_factory=list)  # in the zip, not named in the chat
    missing_media: list[str] = field(default_factory=list)  # named in the chat, not in the zip


def _unsafe(name: str) -> bool:
    parts = name.replace("\\", "/").split("/")
    return name.startswith(("/", "\\")) or bool(_DRIVE.match(name)) or "\\" in name or ".." in parts


def _read(z: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int, max_ratio: int) -> bytes:
    out = bytearray()
    with z.open(info) as f:
        while chunk := f.read(CHUNK):
            out += chunk
            if len(out) > budget:
                raise ImportRefused("zip_limits")
            if len(out) > RATIO_FLOOR and len(out) > max_ratio * max(info.compress_size, 1):
                raise ImportRefused("zip_limits")
    return bytes(out)


def read_export_zip(data: bytes, *, max_total_bytes: int, max_ratio: int = 100, max_entries: int = 2000) -> ZipExport:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except (zipfile.BadZipFile, zlib.error, EOFError, ValueError, OSError) as exc:
        raise ImportRefused("bad_zip") from exc
    if len(infos) > max_entries:
        raise ImportRefused("zip_limits")

    rejected: list[tuple[str, str]] = []
    warnings: list[str] = []
    files: dict[str, bytes] = {}
    total = 0
    with z:
        for info in infos:
            if info.is_dir():
                continue
            if _unsafe(info.filename):
                rejected.append((info.filename, "unsafe_path"))
                continue
            base = PurePosixPath(info.filename).name
            if base in files:
                warnings.append(f"duplicate_entry:{base}")
                continue
            try:
                content = _read(z, info, max_total_bytes - total, max_ratio)
            except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, OSError) as exc:
                raise ImportRefused("bad_zip") from exc  # corrupt, encrypted or unsupported entry
            total += len(content)
            files[base] = content

    texts = [name for name in files if name.lower().endswith(".txt")]
    named = [name for name in texts if _CHAT_NAME.fullmatch(name)]
    chats = named if len(named) == 1 else texts if len(texts) == 1 else []
    if not chats:
        raise ImportRefused("no_chat_file")
    chat_name = chats[0]
    chat_text = files.pop(chat_name)
    try:
        referenced = {m.attachment_name for m in parse_export(chat_text).messages if m.attachment_name}
    except ImportRefused:
        referenced = set()  # the chat text itself is judged by the preview
    return ZipExport(
        chat_name=chat_name,
        chat_text=chat_text,
        media=files,
        rejected=rejected,
        warnings=warnings,
        unmatched_media=[name for name in files if name not in referenced],
        missing_media=sorted(referenced - set(files)),
    )
