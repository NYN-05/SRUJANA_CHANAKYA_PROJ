"""Phase 11a (deferred, R-01): voice notes. FR-VOI-001, FR-VOI-003, FR-FLG-004, FR-PLM-001, FR-VOI-002 (transcript half).

Run while building 11a: uv run pytest tests/phase_11/test_voice_spec.py -m deferred --gate
"""

from __future__ import annotations

import pytest
from helpers import commit_sample

pytestmark = pytest.mark.deferred
AUDIO = b"OggS" + b"voice" * 400


def fake_transcriber(segments, language="hi"):
    from packages.intelligence.speech import FakeTranscriber, Segment

    return FakeTranscriber([Segment(start_ms=s, end_ms=e, text=t, confidence=c) for s, e, t, c in segments], language=language)


def test_speech_port_returns_ms_segments():
    from packages.intelligence.speech import Transcript

    t = fake_transcriber([(12000, 18000, "bees November tak", 0.91)]).transcribe(AUDIO)
    assert isinstance(t, Transcript) and t.segments[0].start_ms == 12000 and isinstance(t.segments[0].end_ms, int)


def test_transcript_spans_are_separate_leaves(vault):
    from packages.integrity.hashing import TypeByte

    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    note = vault.voice_notes(deal)[0]
    vault.store_transcript(deal, note.id, fake_transcriber([(0, 5000, "kal tak", 0.9), (5000, 9000, "pakka", 0.8)]).transcribe(AUDIO))
    kinds = [l.type_byte for l in vault.leaves(deal)]
    assert kinds.count(TypeByte.TRANSCRIPT_SPAN) == 2 and kinds.count(TypeByte.VOICE_AUDIO) == 1


def test_corrected_transcript_is_a_new_record_and_audio_hash_unchanged(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    note = vault.voice_notes(deal)[0]
    first = vault.store_transcript(deal, note.id, fake_transcriber([(0, 5000, "kal tak", 0.9)]).transcribe(AUDIO))
    audio_leaf = [l for l in vault.leaves(deal) if l.ref_id == note.id][0].leaf_hash
    second = vault.correct_transcript(deal, first.id, segment_index=0, text="parso tak")
    assert second.id != first.id and second.supersedes_id == first.id
    assert [l for l in vault.leaves(deal) if l.ref_id == note.id][0].leaf_hash == audio_leaf


def test_text_versus_voice_contradiction_cites_time_range(supply_playbook):
    from packages.contracts import FlagType
    from packages.intelligence.voice import text_voice_flags

    flags = text_voice_flags(text_value_date="2026-11-15", voice_segments=[(12000, 18000, "bees November", 0.9)], term_key="delivery_date", playbook=supply_playbook)
    f = flags[0]
    assert f.type == FlagType.TEXT_VOICE_CONTRADICTION and "0:12" in f.reason_en and "0:18" in f.reason_en


def test_low_confidence_segment_gives_needs_review(supply_playbook):
    from packages.contracts import FlagType
    from packages.intelligence.voice import text_voice_flags

    flags = text_voice_flags(text_value_date="2026-11-15", voice_segments=[(12000, 18000, "bees November", 0.2)], term_key="delivery_date", playbook=supply_playbook)
    assert flags[0].type == FlagType.NEEDS_REVIEW


def test_safe_mode_keeps_audio_without_transcribing(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    assert vault.voice_notes(deal)[0].status == "not_transcribed"


def test_play_the_moment_returns_exact_clip(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": AUDIO})
    note = vault.voice_notes(deal)[0]
    clip = vault.audio_clip(deal, note.id, start_ms=12000, end_ms=18000)
    assert clip.start_ms == 12000 and clip.end_ms == 18000 and clip.data
