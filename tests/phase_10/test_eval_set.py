"""Phase 10: the labelled eval set (FR-EVL-001, EVALUATION sections 1 and 2, DATASET_CARD; R-04)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from packages.ingest.whatsapp import parse_export
from packages.intelligence.playbooks import load_all

ROOT = Path(__file__).resolve().parents[2]
CHATS = ROOT / "eval" / "chats"
LABELS = ROOT / "eval" / "labels"
STATES = {"stated", "unclear", "contradicted", "missing"}
SLICES = {"en", "hinglish", "kn-en", "voice", "adversarial"}
MIN_CHATS = 30  # R-04 (MVP gate); 100 remains the target before any public accuracy claim


def labels():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(LABELS.glob("*.json"))}


def chats():
    return {p.stem: p for p in sorted(CHATS.glob("*.txt"))}


def test_every_chat_has_a_label_and_back():
    assert set(chats()) == set(labels())


def test_minimum_size_and_spread():
    ls = labels()
    assert len(ls) >= MIN_CHATS
    playbooks = {l["playbook"] for l in ls.values()}
    assert {"supply_order", "freelance"} <= playbooks
    slices = {l["slice"] for l in ls.values()}
    assert {"en", "hinglish"} <= slices and slices <= SLICES
    assert any(l["case"] == "adversarial" for l in ls.values())


def test_held_out_split_exists_and_is_untouched_by_tuning():
    ls = labels()
    held = [k for k, l in ls.items() if l["split"] == "heldout"]
    assert 0.15 <= len(held) / len(ls) <= 0.35
    tuned = json.loads((ROOT / "eval" / "tuning_log.json").read_text(encoding="utf-8"))
    assert not set(held) & set(tuned.get("chat_ids_used_for_tuning", []))


def test_samples_have_gold_labels():
    ls = labels()
    for name in ("sample_clean", "sample_ambiguous", "sample_contradictory"):
        assert name in ls, f"FR-IMP-007: {name} needs a gold label"


@pytest.mark.parametrize("chat_id", sorted(labels()) or ["<none>"])
def test_label_is_valid_against_its_chat(chat_id):
    ls, cs, books = labels(), chats(), load_all(ROOT / "playbooks")
    assert chat_id in ls, "no labels found"
    lab = ls[chat_id]
    assert set(lab) >= {"chat_id", "playbook", "slice", "case", "split", "synthetic", "me", "counterparty", "terms", "flags"}
    assert lab["chat_id"] == chat_id and lab["synthetic"] is True
    pb = books[lab["playbook"]]
    assert set(pb.required_keys) <= set(lab["terms"]) <= {t.key for t in pb.terms}
    parsed = parse_export(cs[chat_id].read_bytes())
    seqs = {m.seq for m in parsed.messages}
    assert {lab["me"], lab["counterparty"]} <= set(parsed.participants)
    for key, gold in lab["terms"].items():
        assert gold["state"] in STATES, (chat_id, key)
        if gold["state"] == "missing":
            assert gold["value"] is None and gold["sources"] == [], (chat_id, key)
        if gold["state"] == "stated":
            assert gold["value"] is not None and gold["sources"], (chat_id, key)
        assert set(gold["sources"]) <= seqs, (chat_id, key)


@pytest.mark.parametrize("path", sorted(CHATS.glob("*.txt")) or [Path("<none>")])
def test_no_real_personal_data(path):
    assert path.exists(), "no eval chats found"
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)", text), "phone number"
    assert not re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text), "Aadhaar-like number"
    assert not re.search(r"[A-Z]{5}\d{4}[A-Z]", text), "PAN-like value"
    assert not re.search(r"[\w.]+@[a-z]+", text), "UPI id or email"
