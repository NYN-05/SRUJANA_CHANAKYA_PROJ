"""Timestamps in hashed records: ``YYYY-MM-DDTHH:MM:SS+HH:MM``, whole seconds, device offset, never Z (Q-63)."""

from __future__ import annotations

from datetime import datetime

from packages.contracts import parse_timestamp

__all__ = ["format_timestamp", "parse_timestamp"]


def format_timestamp(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        raise ValueError("timestamp needs a UTC offset")
    if dt.microsecond:
        raise ValueError("timestamps are whole seconds")
    total = int(offset.total_seconds())
    if total % 60:
        raise ValueError("offset must be whole minutes")
    sign = "-" if total < 0 else "+"
    hours, minutes = divmod(abs(total) // 60, 60)
    return (
        f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
        f"{sign}{hours:02d}:{minutes:02d}"
    )
