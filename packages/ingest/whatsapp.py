"""WhatsApp "Export chat" parser for Android and iPhone formats (FR-IMP-001, 003, 006; THREAT_MODEL T14).

Line oriented and linear time: every pattern is anchored and has no nested quantifiers. A line that
does not start a message joins the previous one. Nothing here writes anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from .errors import ImportRefused

Kind = Literal["text", "media", "deleted", "system"]
DateOrder = Literal["DMY", "MDY"]

_AMPM = r"(?:[   ]?([AaPp])\.?[Mm]\.?)?"
_DATE = r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4}|[0-9]{2}), ([0-9]{1,2}):([0-9]{2})"
ANDROID = re.compile(_DATE + _AMPM + r" - (.*)")
IPHONE = re.compile(r"\[" + _DATE + r":([0-9]{2})" + _AMPM + r"\] (.*)")

# Known system notices, checked on the whole line body BEFORE splitting on the first ": ".
# A notice that names a subject (``Raju added Meena``) only counts when the subject has no ": ",
# so "Raju: we added extras" stays a message.
_NOTICES = [
    re.compile(p)
    for p in (
        r"Messages and calls are end-to-end encrypted\b.*",
        r"Messages to this (?:chat|group) are now secured with end-to-end encryption\b.*",
        r"Your security code with .+ changed\b.*",
    )
]
_SUBJECT_NOTICES = [
    re.compile(r"(.+?) " + p)
    for p in (
        r"created group .*",
        r"added .+",
        r"removed .+",
        r"left",
        r"joined using this group's invite link",
        r"changed the subject.*",
        r"changed this group's icon",
        r"deleted this group's icon",
        r"changed the group description",
        r"changed their phone number.*",
    )
]
_DELETED = {"This message was deleted", "You deleted this message"}
_ATTACHED = re.compile(r"<attached: ([^<>]+)>")
_FILE_ATTACHED = re.compile(r"(\S.*?) \(file attached\)")
_OMITTED = re.compile(r"<Media omitted>|(?:image|audio|video|document|sticker|GIF|Contact card) omitted")
_OFFSET = re.compile(r"([+-])([0-9]{2}):([0-9]{2})")
_MARKS = "‎﻿"
BINARY_INVALID_RATIO = 0.01


@dataclass(frozen=True)
class ParsedEntry:
    seq: int
    line_no: int
    sender: str | None
    ts: datetime | None  # aware; None while the date order is unknown
    text: str
    kind: Kind
    attachment_name: str | None = None


@dataclass(frozen=True)
class ParseResult:
    messages: list[ParsedEntry]
    participants: list[str]
    format: Literal["android", "iphone"]
    date_order: DateOrder | None
    needs_date_order_choice: bool
    unparsed_lines: list[tuple[int, str]]
    parse_ratio: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Header:
    line_no: int
    fmt: Literal["android", "iphone"]
    a: int
    b: int
    year: int
    hour: int
    minute: int
    second: int
    rest: str


def decode_export(data: bytes | str) -> tuple[str, list[str]]:
    """Bytes (a file) or str (pasted text) to text with LF line endings; refuses empty and binary input."""
    warnings: list[str] = []
    if isinstance(data, bytes):
        if b"\x00" in data:
            raise ImportRefused("binary")
        text = data.decode("utf-8", errors="replace")
        invalid = text.count("�") - data.count("�".encode())
        # One stray invalid sequence is always tolerated; above that, more than 1% of the bytes means binary.
        if invalid > 1 and invalid > len(data) * BINARY_INVALID_RATIO:
            raise ImportRefused("binary")
        if invalid:
            warnings.append("invalid_utf8")
    else:
        if "\x00" in data:
            raise ImportRefused("binary")
        text = data
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ImportRefused("empty")
    return text, warnings


def _tz(utc_offset: str) -> timezone:
    m = _OFFSET.fullmatch(utc_offset)
    if not m or int(m.group(2)) > 23 or int(m.group(3)) > 59:
        raise ValueError("utc_offset must look like +05:30")
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return timezone(-delta if m.group(1) == "-" else delta)


def _header(line_no: int, line: str) -> _Header | None:
    for fmt, pattern in (("android", ANDROID), ("iphone", IPHONE)):
        m = pattern.fullmatch(line)
        if not m:
            continue
        g = m.groups()
        a, b, year, hour, minute = int(g[0]), int(g[1]), int(g[2]), int(g[3]), int(g[4])
        second = int(g[5]) if fmt == "iphone" else 0
        ampm = g[6] if fmt == "iphone" else g[5]
        if ampm:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if ampm in "Pp" else 0)
        if hour > 23 or minute > 59 or second > 59:
            return None
        return _Header(line_no, fmt, a, b, year + 2000 if year < 100 else year, hour, minute, second, g[-1])  # type: ignore[arg-type]
    return None


def _timestamp(h: _Header, order: DateOrder | None, tz: timezone) -> datetime | None:
    day, month = (h.a, h.b) if order == "DMY" else (h.b, h.a)
    try:
        return datetime(h.year, month, day, h.hour, h.minute, h.second, tzinfo=tz)
    except ValueError:
        return None


def _is_notice(text: str) -> bool:
    if any(p.fullmatch(text) for p in _NOTICES):
        return True
    for p in _SUBJECT_NOTICES:
        m = p.fullmatch(text)
        if m and ": " not in m.group(1) + " ":  # the pattern consumed the space after the subject
            return True
    return False


def _split(h: _Header) -> tuple[str | None, str, Kind]:
    """(sender, body, kind) of a header line; system notices have no sender."""
    rest = h.rest.lstrip(_MARKS)
    if _is_notice(rest):
        return None, rest, "system"
    if ": " in rest:
        sender, body = rest.split(": ", 1)
    elif rest.endswith(":"):
        sender, body = rest[:-1], ""
    else:
        return None, rest, "system"  # WhatsApp writes only notices without "Sender: "
    sender = sender.strip(_MARKS + " ")
    if h.fmt == "iphone" and body.startswith("‎") and _is_notice(body.lstrip(_MARKS)):
        return None, body.lstrip(_MARKS), "system"  # iPhone notices carry the chat name as sender
    return sender, body.lstrip(_MARKS), "text"


def _kind(first_line: str) -> tuple[Kind, str | None]:
    line = first_line.strip(_MARKS + " ")
    if line in _DELETED:
        return "deleted", None
    if m := _ATTACHED.fullmatch(line):
        return "media", m.group(1)
    if m := _FILE_ATTACHED.fullmatch(line):
        return "media", m.group(1)
    if _OMITTED.fullmatch(line):
        return "media", None
    return "text", None


def _infer_order(headers: list[_Header]) -> tuple[DateOrder | None, bool]:
    """(order, mixed): any first field above 12 means day-first, any second above 12 means month-first."""
    day_first = any(h.a > 12 for h in headers)
    month_first = any(h.b > 12 for h in headers)
    if day_first and month_first:
        return None, True
    return ("DMY" if day_first else "MDY" if month_first else None), False


def parse_export(
    data: bytes | str, *, date_order: DateOrder | None = None, utc_offset: str = "+05:30"
) -> ParseResult:
    """Parse an export file (bytes) or pasted text (str). Bad input raises ImportRefused only; bad arguments ValueError."""
    if date_order not in (None, "DMY", "MDY"):
        raise ValueError("date_order must be 'DMY', 'MDY' or None")
    text, warnings = decode_export(data)
    tz = _tz(utc_offset)
    lines = text.split("\n")
    headers: dict[int, _Header] = {}
    impossible: set[int] = set()  # header-shaped lines whose date or time cannot exist
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip(_MARKS)
        h = _header(i, stripped)
        if h and (_timestamp(h, "DMY", tz) or _timestamp(h, "MDY", tz)):
            headers[i] = h
        elif h or ANDROID.fullmatch(stripped) or IPHONE.fullmatch(stripped):
            impossible.add(i)
    if not headers:
        raise ImportRefused("not_whatsapp")
    order = date_order
    if order is None:
        order, mixed = _infer_order(list(headers.values()))
        if mixed:
            warnings.append("mixed_date_order")

    unparsed: list[tuple[int, str]] = []
    entries: list[dict[str, Any]] = []
    for i, line in enumerate(lines, start=1):
        h = headers.get(i)
        ts = _timestamp(h, order, tz) if h and order else None
        if h and (order is None or ts):
            sender, body, kind = _split(h)
            entries.append({"line_no": i, "sender": sender, "ts": ts, "lines": [body], "kind": kind})
        elif h or i in impossible or not entries:
            if line.strip():
                unparsed.append((i, line))  # impossible header date, or text before the first message
        else:
            entries[-1]["lines"].append(line)

    messages, participants = [], []
    for seq, e in enumerate(entries, start=1):
        body_lines = e["lines"]
        while len(body_lines) > 1 and not body_lines[-1].strip():
            body_lines.pop()  # trailing blank lines are not part of the message
        kind, attachment = (e["kind"], None) if e["kind"] == "system" else _kind(body_lines[0])
        messages.append(ParsedEntry(seq, e["line_no"], e["sender"], e["ts"], "\n".join(body_lines), kind, attachment))
        if e["sender"] is not None and e["sender"] not in participants:
            participants.append(e["sender"])

    non_empty = sum(1 for line in lines if line.strip())
    first = headers[min(headers)]
    return ParseResult(
        messages=messages,
        participants=participants,
        format=first.fmt,
        date_order=order,
        needs_date_order_choice=order is None,
        unparsed_lines=unparsed,
        parse_ratio=(non_empty - len(unparsed)) / non_empty if non_empty else 0.0,
        warnings=warnings,
    )
