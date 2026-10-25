"""Phase 6: recap hash and echo code bound to the exact text (FR-ECH-001, FR-ECH-004, INTEGRITY_SPEC 7, D1)."""

from __future__ import annotations

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.contracts import DateValue
from packages.ingest.recap import build_recap
from packages.integrity.echo import ALPHABET, echo_code, recap_hash


@pytest.fixture
def deal(vault):
    deal_id, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal_id)
    vault.correct_term(deal_id, "delivery_date", DateValue(date="2026-11-15"))
    return deal_id


def make_recap(vault, deal, playbook, lang="en"):
    v = vault.create_version(deal) if not vault.versions(deal) else vault.versions(deal)[-1]
    draft = build_recap(vault.agreed_terms(deal), playbook, lang, "Meena", deal_id=deal, version_n=v.n)
    return vault.create_recap(deal, v.n, draft)


def content_of(r):
    return {
        "deal_id": r.deal_id,
        "version_n": r.version_n,
        "language": r.language,
        "lines": [{"term_key": l.term_key, "text": l.text, "sources": l.sources} for l in r.lines],
        "body_text": r.body_text,
    }


def test_hash_covers_content_not_code_or_sent_text(vault, deal, supply_playbook):
    r = make_recap(vault, deal, supply_playbook)
    assert r.recap_hash == recap_hash(content_of(r))
    assert r.echo_code == echo_code(r.recap_hash)
    assert len(r.echo_code) == 4 and set(r.echo_code) <= set(ALPHABET)
    assert r.text == r.body_text + "\n" + f"If all correct, reply: CONFIRM {r.echo_code}"


def test_same_content_same_code(vault, deal, supply_playbook):
    a = make_recap(vault, deal, supply_playbook)
    b = make_recap(vault, deal, supply_playbook)
    assert a.echo_code == b.echo_code and a.recap_hash == b.recap_hash


def test_language_changes_the_code(vault, deal, supply_playbook):
    en = make_recap(vault, deal, supply_playbook, "en")
    hi = make_recap(vault, deal, supply_playbook, "hi")
    assert en.recap_hash != hi.recap_hash


def test_new_version_new_code(vault, deal, supply_playbook):
    r1 = make_recap(vault, deal, supply_playbook)
    vault.correct_term(deal, "delivery_date", DateValue(date="2026-11-22"))
    vault.create_version(deal)
    r2 = make_recap(vault, deal, supply_playbook)
    assert r2.version_n == 2 and r2.echo_code != r1.echo_code


def test_recap_for_unknown_version_refused(vault, deal, supply_playbook):
    draft = build_recap(vault.agreed_terms(deal), supply_playbook, "en", "Meena", deal_id=deal, version_n=9)
    with pytest.raises((KeyError, ValueError)):
        vault.create_recap(deal, 9, draft)


def test_recap_rows_are_insert_only_and_audited(vault, deal, supply_playbook):
    make_recap(vault, deal, supply_playbook)
    assert vault.audit_events(deal)[-1].action == "send_recap"
