"""Phase 2: shipped sample chats (FR-IMP-007)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from packages.ingest.samples import list_samples, load_sample
from packages.ingest.whatsapp import parse_export

ROOT = Path(__file__).resolve().parents[2]


def test_three_samples_listed():
    assert set(list_samples()) >= {"clean", "ambiguous", "contradictory"}


@pytest.mark.parametrize("name", ["clean", "ambiguous", "contradictory"])
def test_sample_parses_with_known_date_order(name):
    r = parse_export(load_sample(name))
    assert r.date_order in {"DMY", "MDY"}
    assert len(r.participants) == 2
    assert r.unparsed_lines == []


def test_ambiguous_sample_content_matches_the_demo():
    text = load_sample("ambiguous").decode("utf-8").lower()
    assert "next week" in text
    assert "balance" not in text and "penalty" not in text and "late" not in text
    first = parse_export(load_sample("ambiguous")).messages[0]
    assert first.kind == "text" and first.seq == 1  # I-10: demo numbering starts at #1


def test_contradictory_sample_has_two_prices():
    text = load_sample("contradictory").decode("utf-8")
    assert "50,000" in text and "45,000" in text


@pytest.mark.parametrize("name", ["clean", "ambiguous", "contradictory"])
def test_samples_are_synthetic(name):
    text = load_sample(name).decode("utf-8")
    assert not re.search(r"\+?91[\s-]?\d{10}|\b\d{10}\b", text), "no phone numbers"
    assert not re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text), "no Aadhaar-like numbers"
    assert "@" not in text, "no UPI ids or emails"


def test_unknown_sample_raises():
    with pytest.raises(KeyError):
        load_sample("does-not-exist")


def test_sample_names_cannot_escape_the_folder():
    for bad in ("../clean", "clean.txt", "/etc/passwd"):
        with pytest.raises(KeyError):
            load_sample(bad)


@pytest.mark.parametrize("name", ["clean", "ambiguous", "contradictory"])
def test_sample_copies_are_identical(name):
    raw = load_sample(name)
    assert (ROOT / "tests" / "fixtures" / "chats" / f"{name}.txt").read_bytes() == raw
    assert (ROOT / "eval" / "chats" / f"sample_{name}.txt").read_bytes() == raw


@pytest.mark.parametrize("name", ["clean", "ambiguous", "contradictory"])
def test_sample_gold_label_matches_its_chat(name):
    label = json.loads((ROOT / "eval" / "labels" / f"sample_{name}.json").read_text(encoding="utf-8"))
    r = parse_export(load_sample(name))
    assert label["chat_id"] == f"sample_{name}" and label["synthetic"] is True and label["case"] == name
    assert {label["me"], label["counterparty"]} == set(r.participants)
    seqs = {m.seq for m in r.messages}
    for key, gold in label["terms"].items():
        assert set(gold["sources"]) <= seqs, key
        assert (gold["value"] is None) == (gold["state"] in {"missing", "contradicted"}), key
