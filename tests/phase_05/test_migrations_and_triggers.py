"""Phase 5: Alembic migrations and insert-only triggers (FR-VLT-004, Data Model section 4, ADR-021)."""

from __future__ import annotations

import sqlite3

import pytest
from helpers import commit_sample, confirm_clear_terms

from packages.vault.migrate import upgrade

INSERT_ONLY = [
    "messages",
    "voice_notes",
    "score_snapshots",
    "versions",
    "recaps",
    "confirmations",
    "leaves",
    "receipts",
    "audit_events",
    "import_records",
]


def test_upgrade_head_on_fresh_database(tmp_path):
    db = tmp_path / "fresh.sqlite"
    upgrade(f"sqlite:///{db.as_posix()}")
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    con.close()
    assert set(INSERT_ONLY) <= tables
    assert "alembic_version" in tables


def test_upgrade_is_idempotent(tmp_path):
    url = f"sqlite:///{(tmp_path / 'x.sqlite').as_posix()}"
    upgrade(url)
    upgrade(url)


def test_wal_mode(vault):
    con = sqlite3.connect(vault.db_path)
    assert con.execute("pragma journal_mode").fetchone()[0].lower() == "wal"
    con.close()


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_both_triggers_exist(vault, table):
    con = sqlite3.connect(vault.db_path)
    names = {r[0] for r in con.execute("select name from sqlite_master where type='trigger' and tbl_name=?", (table,))}
    con.close()
    assert f"{table}_no_update" in names and f"{table}_no_delete" in names


@pytest.mark.parametrize("table", ["messages", "leaves", "audit_events", "import_records", "versions", "score_snapshots"])
def test_update_and_delete_are_blocked(vault, table, supply_playbook):
    from packages.contracts import TermState
    from packages.intelligence.score import ScoreInput, compute_score

    deal, _ = commit_sample(vault, "ambiguous.txt", "Raju", "Meena")
    confirm_clear_terms(vault, deal)
    vault.create_version(deal)
    score = compute_score([ScoreInput(key="price", confirmed=True, state=TermState.STATED, acknowledged_by_both=True)], supply_playbook)
    vault.record_score(deal, score, "test")
    con = sqlite3.connect(vault.db_path)
    assert con.execute(f"select count(*) from {table}").fetchone()[0] > 0
    with pytest.raises(sqlite3.DatabaseError):
        con.execute(f"update {table} set rowid = rowid")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute(f"delete from {table}")
    con.close()
