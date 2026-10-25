"""Phase 8 (gated in Phase 10): a real open model on the ambiguous sample (FR-EXT-004, NFR-PERF-004).

Needs VERIDOC_MODEL_PATH (a GGUF file listed in models/manifest.json) and the `model` extra installed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from helpers import sample_draft, terms_by_key

from packages.contracts import TermState
from packages.intelligence.extract import extract_terms
from packages.intelligence.model.models import verify_model_file
from packages.intelligence.model.refine import refine_terms

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def runner():
    path = os.environ.get("VERIDOC_MODEL_PATH")
    assert path, "set VERIDOC_MODEL_PATH to run the model gate"
    p = Path(path)
    manifest = json.loads((ROOT / "models" / "manifest.json").read_text(encoding="utf-8"))
    entry = next((e for e in manifest["models"] if e["file"] == p.name), None)
    assert entry, f"{p.name} is not listed in models/manifest.json"
    assert verify_model_file(p, entry), "model hash does not match the manifest"
    from packages.intelligence.model.llama_cpp import LlamaCppRunner

    return LlamaCppRunner(p)


def test_refine_ambiguous_sample_within_budget(runner, supply_playbook):
    d = sample_draft("ambiguous.txt", "Raju", "Meena")
    kw = dict(me_id=d.me_id, counterparty_id=d.counterparty_id, eligible_ids=d.eligible_message_ids)
    rules = extract_terms(d.messages, supply_playbook, date_order="DMY", **kw)
    runner.generate("warm-up", "[]", {"type": "object"}, timeout_s=120)  # load outside the timed part
    start = time.perf_counter()
    result = refine_terms(rules, d.messages, supply_playbook, runner, timeout_s=30, **kw)
    elapsed = time.perf_counter() - start
    assert result.error is None, result.error
    assert elapsed < 30, f"{elapsed:.1f}s (target NFR-PERF-004: under 10 s on an 8 GB laptop)"
    t = terms_by_key(result.terms)
    assert t["price"].value.paise == "48000"
    assert t["final_payment"].state in (TermState.MISSING, TermState.UNCLEAR) or t["final_payment"].needs_review


def test_real_model_obeys_no_injection(runner, supply_playbook):
    d = sample_draft("injection.txt", "Raju", "Meena")
    kw = dict(me_id=d.me_id, counterparty_id=d.counterparty_id, eligible_ids=d.eligible_message_ids)
    rules = extract_terms(d.messages, supply_playbook, date_order="DMY", **kw)
    result = refine_terms(rules, d.messages, supply_playbook, runner, timeout_s=30, **kw)
    assert terms_by_key(result.terms)["price"].value.paise == "48000"
