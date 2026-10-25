"""Phase 1: timestamp format for hashed records (INTEGRITY_SPEC section 4, Q-63)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.integrity.timestamp import format_timestamp, parse_timestamp

IST = timezone(timedelta(hours=5, minutes=30))


def test_format_keeps_device_offset():
    assert format_timestamp(datetime(2026, 10, 12, 10, 2, 0, tzinfo=IST)) == "2026-10-12T10:02:00+05:30"


def test_format_utc_as_plus_zero_never_z():
    assert format_timestamp(datetime(2026, 10, 12, 4, 32, tzinfo=timezone.utc)) == "2026-10-12T04:32:00+00:00"


def test_format_negative_offset():
    tz = timezone(timedelta(hours=-3, minutes=-30))
    assert format_timestamp(datetime(2026, 1, 2, 3, 4, 5, tzinfo=tz)) == "2026-01-02T03:04:05-03:30"


def test_format_rejects_naive_datetime():
    with pytest.raises(ValueError):
        format_timestamp(datetime(2026, 10, 12, 10, 2))


def test_format_rejects_fractional_seconds():
    with pytest.raises(ValueError):
        format_timestamp(datetime(2026, 10, 12, 10, 2, 0, 500, tzinfo=IST))


def test_parse_round_trip():
    text = "2026-10-12T10:02:00+05:30"
    dt = parse_timestamp(text)
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)
    assert format_timestamp(dt) == text


@pytest.mark.parametrize(
    "bad",
    [
        "2026-10-12T10:02:00Z",
        "2026-10-12T10:02:00",
        "2026-10-12T10:02:00.000+05:30",
        "2026-10-12T10:02:00-00:00",
        "2026-02-30T10:02:00+05:30",
        "2026-10-12T24:00:00+05:30",
        "2026-10-12T10:02:00+25:00",
        "2026-10-12T10:02+05:30",
        "20261012T100200+0530",
        "",
    ],
)
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        parse_timestamp(bad)


def test_parse_leap_day():
    assert parse_timestamp("2028-02-29T00:00:00+05:30").day == 29


def test_format_rejects_offset_with_seconds():
    with pytest.raises(ValueError):
        format_timestamp(datetime(2026, 10, 12, 10, 2, tzinfo=timezone(timedelta(hours=5, seconds=30))))


def test_parse_rejects_non_ascii_digits_and_trailing_newline():
    for bad in ("२०२६-10-12T10:02:00+05:30", "2026-10-12T10:02:00+05:30\n"):
        with pytest.raises(ValueError):
            parse_timestamp(bad)


def test_round_trip_across_offsets():
    for text in ("2026-12-31T23:59:59+14:00", "2026-01-01T00:00:00-12:00", "2026-06-15T12:00:00+00:00"):
        assert format_timestamp(parse_timestamp(text)) == text
