"""Phase 5: import commit, leaves and crash safety (FR-VLT-001, FR-VLT-006, FR-VOI-002 audio, FR-IMP-002)."""

from __future__ import annotations

import hashlib

import pytest
from helpers import CHATS, chat_of, commit_sample, sample_draft

from packages.contracts import MessageOrigin
from packages.ingest.commit import prepare_commit
from packages.ingest.whatsapp import parse_export
from packages.integrity.hashing import TypeByte, leaf_hash, payload_digest_bytes, payload_digest_json
from packages.integrity.merkle import merkle_root
from packages.vault import faults

MESSAGE_FIELDS = {"id", "deal_id", "seq", "sender_id", "ts", "text", "attachment_hash", "is_system", "origin"}


def test_142_messages_give_142_reproducible_leaves(vault):
    raw = chat_of(142)
    draft = prepare_commit(parse_export(raw), me="Raju", counterparty="Meena", playbook_key="supply_order", origin=MessageOrigin.EXPORT)
    deal = vault.commit_import(draft, export_bytes=raw, file_name="c.txt", media={})
    leaves = [l for l in vault.leaves(deal) if l.type_byte == TypeByte.MESSAGE]
    assert len(leaves) == 142
    assert [l.seq for l in vault.leaves(deal)] == list(range(1, len(vault.leaves(deal)) + 1))
    for leaf in leaves:
        assert len(leaf.salt) == 16
        assert set(leaf.payload) == MESSAGE_FIELDS  # INTEGRITY_SPEC 4.2: every Message field, nothing else
        assert payload_digest_json(leaf.payload) == leaf.payload_digest
        assert leaf_hash(TypeByte.MESSAGE, leaf.salt, leaf.payload_digest) == leaf.leaf_hash


def test_salts_are_unique(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    salts = [l.salt for l in vault.leaves(deal)]
    assert len(set(salts)) == len(salts)


def test_import_record_has_raw_export_digest(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    rec = vault.import_record(deal)
    assert rec.export_digest == hashlib.sha256((CHATS / "ambiguous.txt").read_bytes()).hexdigest()
    assert rec.message_count == 5 and rec.file_name == "ambiguous.txt"


def test_messages_round_trip(vault):
    deal, draft = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    assert vault.messages(deal) == draft.messages


def test_media_stored_encrypted_by_digest_once(vault):
    audio = b"OggS" + bytes(range(256)) * 40
    img = b"\xff\xd8" + b"jpeg" * 100
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": audio, "b.jpg": img, "copy.opus": audio})
    digest = hashlib.sha256(audio).hexdigest()
    path = vault.evidence_path(digest)
    assert path.name == digest and path.parent.name == digest[:2]
    assert path.is_file() and audio not in path.read_bytes()
    assert len([p for p in (vault.home / "evidence").rglob("*") if p.is_file()]) == 2
    kinds = [l.type_byte for l in vault.leaves(deal)]
    assert kinds.count(TypeByte.VOICE_AUDIO) == 2 and kinds.count(TypeByte.ATTACHMENT) == 1
    audio_leaf = next(l for l in vault.leaves(deal) if l.type_byte == TypeByte.VOICE_AUDIO)
    assert audio_leaf.payload_digest == payload_digest_bytes(audio)


def test_audio_is_kept_but_not_transcribed(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena", media={"a.opus": b"OggS-audio"})
    notes = vault.voice_notes(deal)
    assert len(notes) == 1 and notes[0].status == "not_transcribed"  # R-01


def test_import_writes_audit_event(vault):
    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    actions = [e.action for e in vault.audit_events(deal)]
    assert actions.count("import") == 1


def test_crash_mid_import_leaves_nothing(vault):
    raw = (CHATS / "ambiguous.txt").read_bytes()
    draft = sample_draft("ambiguous.txt", "Raju", "Meena")
    before = len(vault.deals())
    with faults.inject("import.after_messages"):
        with pytest.raises(faults.InjectedFault):
            vault.commit_import(draft, export_bytes=raw, file_name="a.txt", media={"a.opus": b"OggS"})
    assert len(vault.deals()) == before
    assert all(r.ok for r in vault.self_check())
    assert not [p for p in (vault.home / "evidence").rglob("*") if p.is_file()]


def test_second_import_into_new_deal_has_its_own_tree(vault):
    d1, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    d2, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    assert d1 != d2
    r1 = merkle_root([l.leaf_hash for l in vault.leaves(d1)])
    r2 = merkle_root([l.leaf_hash for l in vault.leaves(d2)])
    assert r1 != r2  # different salts and ids
