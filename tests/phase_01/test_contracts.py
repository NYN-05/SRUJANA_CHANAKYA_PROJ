"""Phase 1: shared contract models (PHASES.md Appendix A.1; INTEGRITY_SPEC section 4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

GOOD_TS = "2026-10-12T10:02:00+05:30"
HEX64 = "a" * 64


def _message(**over):
    from packages.contracts import Message, MessageOrigin

    data = dict(
        id="00000000-0000-4000-8000-000000000001",
        deal_id="00000000-0000-4000-8000-0000000000aa",
        seq=1,
        sender_id="Raju",
        ts=GOOD_TS,
        text="200 shirts, 480 each ok?",
        attachment_hash=None,
        is_system=False,
        origin=MessageOrigin.EXPORT,
    )
    data.update(over)
    return Message(**data)


def test_contract_version_is_set():
    from packages.contracts import CONTRACT_VERSION

    assert isinstance(CONTRACT_VERSION, str) and CONTRACT_VERSION


def test_message_accepts_valid_record():
    m = _message()
    assert m.seq == 1 and m.ts == GOOD_TS


@pytest.mark.parametrize(
    "bad_ts",
    [
        "2026-10-12T10:02:00Z",
        "2026-10-12T10:02:00",
        "2026-10-12T10:02:00.5+05:30",
        "2026-10-12T10:02:00-00:00",
        "2026-02-30T10:02:00+05:30",
        "2026-10-12 10:02:00+05:30",
        "12/10/2026 10:02",
    ],
)
def test_message_rejects_bad_timestamps(bad_ts):
    with pytest.raises(ValidationError):
        _message(ts=bad_ts)


def test_utc_written_as_plus_zero_is_valid():
    assert _message(ts="2026-10-12T04:32:00+00:00").ts.endswith("+00:00")


@pytest.mark.parametrize("seq", [0, -1])
def test_seq_starts_at_one(seq):
    with pytest.raises(ValidationError):
        _message(seq=seq)


@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "g" * 64, "0x" + "a" * 62])
def test_attachment_hash_is_lowercase_hex64(bad):
    with pytest.raises(ValidationError):
        _message(attachment_hash=bad)


def test_attachment_hash_accepts_hex64():
    assert _message(attachment_hash=HEX64).attachment_hash == HEX64


def test_message_origin_values():
    from packages.contracts import MessageOrigin

    assert {o.value for o in MessageOrigin} == {"export", "paste", "simulator"}


def test_money_is_paise_digit_string():
    from packages.contracts import MoneyValue

    assert MoneyValue(paise="4800000").paise == "4800000"
    for bad in ("48000.00", "-100", "4,800", "", "1e5"):
        with pytest.raises(ValidationError):
            MoneyValue(paise=bad)


def test_term_state_values_and_labels():
    from packages.contracts import TERM_STATE_LABELS, TermState

    assert {s.value for s in TermState} == {"stated", "unclear", "contradicted", "missing"}
    assert TERM_STATE_LABELS[TermState.STATED] == ("✓", "Clear")
    assert TERM_STATE_LABELS[TermState.UNCLEAR] == ("!", "Ambiguous")
    assert TERM_STATE_LABELS[TermState.CONTRADICTED] == ("⚠", "Conflict")
    assert TERM_STATE_LABELS[TermState.MISSING] == ("○", "Missing")


def test_origin_tone_confirmation_enums():
    from packages.contracts import ConfirmationState, Origin, Tone

    assert {o.value for o in Origin} == {"rules", "ai", "both", "user"}
    assert {t.value for t in Tone} == {"casual", "polite", "firm"}
    assert {c.value for c in ConfirmationState} == {"sent", "confirmed", "not_confirmed"}


def test_flag_types_match_prd_table():
    from packages.contracts import FlagType

    assert {f.name for f in FlagType} >= {
        "AMBIGUOUS_DATE",
        "AMBIGUOUS_AMOUNT",
        "VAGUE_QUANTITY",
        "VAGUE_PAYMENT",
        "MISSING_TERM",
        "CONTRADICTION",
        "TEXT_VOICE_CONTRADICTION",
        "UNACKNOWLEDGED",
        "NEEDS_REVIEW",
        "REGISTRATION_HINT",
    }


def test_date_values():
    from packages.contracts import DateValue, PartialDateValue

    assert DateValue(date="2026-11-15").date == "2026-11-15"
    assert PartialDateValue(date="--11-15").date == "--11-15"
    with pytest.raises(ValidationError):
        DateValue(date="--11-15")
    with pytest.raises(ValidationError):
        DateValue(date="2026-13-01")


def test_quantity_value_is_integer():
    from packages.contracts import QuantityValue

    assert QuantityValue(amount=200, unit="shirts").amount == 200
    with pytest.raises(ValidationError):
        QuantityValue(amount=1.5, unit="kg")


def test_proposed_term_round_trips_json():
    from packages.contracts import MoneyValue, Origin, ProposedTerm, SourceRef, TermState

    term = ProposedTerm(
        key="price",
        value=MoneyValue(paise="48000", per="item"),
        raw="480 each",
        state=TermState.STATED,
        sources=[SourceRef(kind="message", message_id="m1", seq=1, start=12, end=20, quote="480 each")],
        candidates=[],
        origin=Origin.RULES,
        confidence="high",
        needs_review=False,
        unclear_reason=None,
        readings=[],
    )
    again = ProposedTerm.model_validate_json(term.model_dump_json())
    assert again == term


def test_import_record_digest_is_hex64():
    from packages.contracts import ImportRecord

    rec = ImportRecord(deal_id="d1", export_digest=HEX64, file_name="chat.txt", message_count=5, imported_at=GOOD_TS)
    assert rec.message_count == 5
    with pytest.raises(ValidationError):
        ImportRecord(deal_id="d1", export_digest="xyz", file_name="chat.txt", message_count=5, imported_at=GOOD_TS)


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        _message(sender="Raju")


def test_partial_date_allows_leap_day_but_not_impossible_days():
    from packages.contracts import PartialDateValue

    assert PartialDateValue(date="--02-29").date == "--02-29"
    for bad in ("--02-30", "--13-01", "2026-11-15", "11-15"):
        with pytest.raises(ValidationError):
            PartialDateValue(date=bad)


@pytest.mark.parametrize("bad", ["007", "1.0", " 100", "١٠٠"])
def test_paise_is_canonical_ascii_digits(bad):
    from packages.contracts import MoneyValue

    with pytest.raises(ValidationError):
        MoneyValue(paise=bad)


def test_source_ref_span_order():
    from packages.contracts import SourceRef

    with pytest.raises(ValidationError):
        SourceRef(message_id="m1", seq=1, start=5, end=4, quote="x")
    with pytest.raises(ValidationError):
        SourceRef(message_id="m1", seq=0, start=0, end=1, quote="x")


def test_term_value_is_discriminated_by_kind():
    from packages.contracts import AgreedTerm, PaymentValue

    term = AgreedTerm.model_validate(
        {
            "key": "advance",
            "value": {"kind": "payment", "paise": "4800000", "when": "paid"},
            "sources": [],
            "confirmed_by": "me",
            "confirmed_at": GOOD_TS,
            "origin": "rules",
        }
    )
    assert isinstance(term.value, PaymentValue) and term.acknowledged_by_other is False
    with pytest.raises(ValidationError):
        AgreedTerm.model_validate(term.model_dump() | {"value": {"kind": "unknown"}})
    with pytest.raises(ValidationError):
        PaymentValue(when="someday")


def test_recap_echo_code_uses_the_crockford_alphabet():
    from packages.contracts import Recap

    base = dict(id="r1", deal_id="d1", version_n=1, language="en", lines=[], body_text="Hi", recap_hash=bytes(32), text="Hi")
    assert Recap(**base, echo_code="7F3K").echo_code == "7F3K"
    for bad in ("7F3U", "7f3k", "7F3", "O1LI"):
        with pytest.raises(ValidationError):
            Recap(**base, echo_code=bad)


def test_verify_result_shapes():
    from packages.contracts import FirstDifference, VerifyCheck, VerifyResult

    r = VerifyResult(verdict="ALTERED", checks=[VerifyCheck(name="merkle_root", ok=False)], first_difference=FirstDifference(kind="root"))
    assert r.first_difference.seq is None and r.warnings == []
    with pytest.raises(ValidationError):
        VerifyResult(verdict="MAYBE", checks=[])
    with pytest.raises(ValidationError):
        FirstDifference(kind="unknown")


def test_contract_timestamp_parser_is_the_integrity_one():
    from packages.contracts import parse_timestamp as contract_parse
    from packages.integrity.timestamp import parse_timestamp

    assert parse_timestamp is contract_parse
