"""What the parser understood, shown before anything is created (FR-IMP-003, FR-IMP-009)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from .errors import ImportRefused
from .whatsapp import DateOrder, parse_export

FORMAT_PROBLEM_RATIO = 0.8
MAX_UNPARSED_SHOWN = 5


@dataclass(frozen=True)
class ImportPreview:
    file_name: str
    message_count: int  # text entries
    media_count: int
    participants: list[str]
    date_range: tuple[datetime | None, datetime | None]
    date_order: DateOrder | None
    needs_date_order_choice: bool
    format_problem: bool
    first_unparsed_lines: list[tuple[int, str]]
    warnings: list[str]
    export_digest: str  # hex SHA-256 of the raw bytes, no normalisation (INTEGRITY_SPEC 4.1)


def build_preview(data: bytes, file_name: str, *, max_bytes: int, date_order: DateOrder | None = None) -> ImportPreview:
    if len(data) > max_bytes:
        raise ImportRefused("too_large")
    r = parse_export(data, date_order=date_order)
    stamps = [m.ts for m in r.messages if m.ts is not None]
    return ImportPreview(
        file_name=file_name,
        message_count=sum(m.kind == "text" for m in r.messages),
        media_count=sum(m.kind == "media" for m in r.messages),
        participants=r.participants,
        date_range=(min(stamps), max(stamps)) if stamps else (None, None),
        date_order=r.date_order,
        needs_date_order_choice=r.needs_date_order_choice,
        format_problem=r.parse_ratio < FORMAT_PROBLEM_RATIO,
        first_unparsed_lines=r.unparsed_lines[:MAX_UNPARSED_SHOWN],
        warnings=r.warnings,
        export_digest=hashlib.sha256(data).hexdigest(),
    )
