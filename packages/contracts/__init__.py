"""Shared contract models used by every package (PHASES.md Appendix A.1; INTEGRITY_SPEC section 4).

Timestamps are text in ``YYYY-MM-DDTHH:MM:SS+HH:MM``; money is integer paise as a digit string;
durations are integer milliseconds (I-15). Field names here are the hashed field names (D4).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

CONTRACT_VERSION = "1.0"

_TS = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})([+-])([0-9]{2}):([0-9]{2})")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_PARTIAL_DATE = re.compile(r"--([0-9]{2})-([0-9]{2})")


def parse_timestamp(text: str) -> datetime:
    """Read the hashed-record timestamp form; reject ``Z``, no offset, fractions, ``-00:00`` and impossible values."""
    m = _TS.fullmatch(text) if isinstance(text, str) else None
    if not m:
        raise ValueError("timestamp must be YYYY-MM-DDTHH:MM:SS+HH:MM")
    year, month, day, hour, minute, second, sign, off_h, off_m = m.groups()
    if sign == "-" and off_h == off_m == "00":
        raise ValueError("offset -00:00 is not allowed; write +00:00")
    if int(off_h) > 23 or int(off_m) > 59:
        raise ValueError("offset out of range")
    offset = timedelta(hours=int(off_h), minutes=int(off_m))
    tz = timezone(-offset if sign == "-" else offset)
    return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=tz)


def _check_timestamp(text: str) -> str:
    parse_timestamp(text)
    return text


def _check_date(text: str) -> str:
    if not _DATE.fullmatch(text):
        raise ValueError("date must be YYYY-MM-DD")
    date.fromisoformat(text)
    return text


def _check_partial_date(text: str) -> str:
    m = _PARTIAL_DATE.fullmatch(text)
    if not m:
        raise ValueError("partial date must be --MM-DD")
    date(2000, int(m.group(1)), int(m.group(2)))  # leap year, so --02-29 is allowed
    return text


Timestamp = Annotated[str, AfterValidator(_check_timestamp)]
IsoDate = Annotated[str, AfterValidator(_check_date)]
Hex64 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Paise = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$")]
Seq = Annotated[int, Field(ge=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- enums ----


class TermState(str, Enum):
    STATED = "stated"
    UNCLEAR = "unclear"
    CONTRADICTED = "contradicted"
    MISSING = "missing"


TERM_STATE_LABELS: dict[TermState, tuple[str, str]] = {
    TermState.STATED: ("✓", "Clear"),
    TermState.UNCLEAR: ("!", "Ambiguous"),
    TermState.CONTRADICTED: ("⚠", "Conflict"),
    TermState.MISSING: ("○", "Missing"),
}


class Origin(str, Enum):
    RULES = "rules"
    AI = "ai"
    BOTH = "both"
    USER = "user"


class MessageOrigin(str, Enum):
    EXPORT = "export"
    PASTE = "paste"
    SIMULATOR = "simulator"


class FlagType(str, Enum):
    """PRD section 8.4."""

    AMBIGUOUS_DATE = "AMBIGUOUS_DATE"
    AMBIGUOUS_AMOUNT = "AMBIGUOUS_AMOUNT"
    VAGUE_QUANTITY = "VAGUE_QUANTITY"
    VAGUE_PAYMENT = "VAGUE_PAYMENT"
    MISSING_TERM = "MISSING_TERM"
    CONTRADICTION = "CONTRADICTION"
    TEXT_VOICE_CONTRADICTION = "TEXT_VOICE_CONTRADICTION"
    UNACKNOWLEDGED = "UNACKNOWLEDGED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REGISTRATION_HINT = "REGISTRATION_HINT"


class Tone(str, Enum):
    CASUAL = "casual"
    POLITE = "polite"
    FIRM = "firm"


class ConfirmationState(str, Enum):
    SENT = "sent"
    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"


# ---- messages and imports ----


class Message(Contract):
    id: str
    deal_id: str
    seq: Seq
    sender_id: str | None  # None for system notices (Phase 2)
    ts: Timestamp
    text: str
    attachment_hash: Hex64 | None = None
    is_system: bool = False
    origin: MessageOrigin


class ImportRecord(Contract):
    deal_id: str
    export_digest: Hex64
    file_name: str
    message_count: Annotated[int, Field(ge=0)]
    imported_at: Timestamp


# ---- term values (discriminated by kind) ----


class MoneyValue(Contract):
    kind: Literal["money"] = "money"
    paise: Paise
    per: Literal["item", "total"] | None = None


class DateValue(Contract):
    kind: Literal["date"] = "date"
    date: IsoDate


class PartialDateValue(Contract):
    """Month and day only (``--MM-DD``); never part of an agreed version (INTEGRITY_SPEC section 4)."""

    kind: Literal["partial_date"] = "partial_date"
    date: Annotated[str, AfterValidator(_check_partial_date)]


class QuantityValue(Contract):
    kind: Literal["quantity"] = "quantity"
    amount: int
    unit: str | None = None


class PercentValue(Contract):
    kind: Literal["percent"] = "percent"
    basis_points: Annotated[int, Field(ge=0)]


class TextValue(Contract):
    kind: Literal["text"] = "text"
    text: str


class EventValue(Contract):
    kind: Literal["event"] = "event"
    event: str


class PartyValue(Contract):
    kind: Literal["party"] = "party"
    names: list[str]


class PaymentValue(Contract):
    kind: Literal["payment"] = "payment"
    paise: Paise | None = None
    when: Literal["paid", "on_delivery", "after_delivery", "on_date", "on_completion"] | None = None
    days: Annotated[int, Field(ge=0)] | None = None
    date: IsoDate | None = None


TermValue = Annotated[
    MoneyValue | DateValue | PartialDateValue | QuantityValue | PercentValue | TextValue | EventValue | PartyValue | PaymentValue,
    Field(discriminator="kind"),
]


# ---- terms ----


class SourceRef(Contract):
    kind: Literal["message"] = "message"
    message_id: str
    seq: Seq
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=0)]
    quote: str

    @model_validator(mode="after")
    def _span_order(self) -> SourceRef:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self


class Candidate(Contract):
    value: TermValue
    sources: list[SourceRef]


class ProposedTerm(Contract):
    key: str
    value: TermValue | None
    raw: str | None
    state: TermState
    sources: list[SourceRef]
    candidates: list[Candidate] = []
    origin: Origin
    confidence: Literal["high", "medium", "low"]
    needs_review: bool = False
    unclear_reason: str | None = None
    readings: list[TermValue] = []


class AgreedTerm(Contract):
    """Only key, value, sources, confirmed_by and confirmed_at are hashed (INTEGRITY_SPEC 4.2)."""

    key: str
    value: TermValue
    sources: list[SourceRef]
    confirmed_by: str
    confirmed_at: Timestamp
    origin: Origin
    acknowledged_by_other: bool = False


# ---- flags, score, suggestions ----


class Flag(Contract):
    type: FlagType
    term_key: str | None
    reason_en: str
    reason_hi: str
    source_refs: list[SourceRef] = []
    rule_id: str


class ScoreRow(Contract):
    key: str
    weight: Decimal
    present: bool
    clear: bool
    acknowledged: bool
    points: Decimal


class ScoreResult(Contract):
    score: int
    rows: list[ScoreRow]
    present_count: int
    clear_count: int
    acknowledged_count: int
    total: int


class Suggestion(Contract):
    target_term_keys: list[str]
    tone: Tone
    language: str
    text: str
    needs_user_input: bool = False


# ---- recap ----


class RecapLine(Contract):
    term_key: str
    text: str
    sources: list[str]  # message ids


class RecapDraft(Contract):
    deal_id: str
    version_n: Seq
    language: str
    lines: list[RecapLine]
    body_text: str
    omitted_terms: list[tuple[str, str]] = []  # (term key, reason)


class Recap(RecapDraft):
    """A draft bound to its echo code. recap_hash covers deal_id, version_n, language, lines and body_text (INTEGRITY_SPEC 4.2)."""

    id: str
    recap_hash: bytes
    echo_code: Annotated[str, StringConstraints(pattern=r"^[0-9A-HJKMNP-TV-Z]{4}$")]
    text: str


# ---- verification ----

DifferenceKind = Literal[
    "message",
    "voice_audio",
    "transcript_span",
    "handshake_seal",
    "attachment",
    "term",
    "confirmation",
    "import_record",
    "chain_link",
    "root",
]


class FirstDifference(Contract):
    kind: DifferenceKind
    seq: Seq | None = None
    version_n: Seq | None = None


class VerifyCheck(Contract):
    name: str
    ok: bool
    detail: str = ""


class VerifyResult(Contract):
    verdict: Literal["UNCHANGED", "ALTERED"]
    checks: list[VerifyCheck]
    first_difference: FirstDifference | None = None
    warnings: list[str] = []
