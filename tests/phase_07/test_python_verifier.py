"""Phase 7: the Python verifier (INTEGRITY_SPEC section 10; FR-VFY-002, FR-VFY-003)."""

from __future__ import annotations

import io
import zipfile

import pytest
from bundle_builder import build_bundle

from packages.integrity.receipt import receipt_hash
from packages.integrity.verify import BundleFormatError, UnsupportedSpecVersion, verify_bundle

CHECK_NAMES = {"spec_version", "leaves", "merkle_root", "chain", "version_roots", "import_record", "timestamps", "anchor"}


def rehash(b, mutate):
    env = b.json("receipt.json")
    mutate(env["body"])
    env["receipt_hash"] = receipt_hash(env["body"]).hex()
    b.set_json("receipt.json", env)
    return b


def test_checks_listed_one_per_line():
    r = verify_bundle(build_bundle().zip_bytes())
    assert {c.name for c in r.checks} == CHECK_NAMES
    for c in r.checks:
        if c.name != "anchor":
            assert c.ok is True, c
    anchor = next(c for c in r.checks if c.name == "anchor")
    assert "not anchored" in anchor.detail.lower()


def test_chain_check_counts_links():
    r = verify_bundle(build_bundle(versions=4).zip_bytes())
    assert "4 of 4" in next(c for c in r.checks if c.name == "chain").detail


def test_accepts_path_or_bytes(tmp_path):
    data = build_bundle().zip_bytes()
    p = tmp_path / "receipt.zip"
    p.write_bytes(data)
    assert verify_bundle(p).verdict == verify_bundle(data).verdict == "UNCHANGED"


def test_bundle_without_versions_verifies_leaves_only():
    assert verify_bundle(build_bundle(versions=0).zip_bytes()).verdict == "UNCHANGED"


def test_single_message_bundle():
    b = build_bundle(n_messages=1, with_audio=False, with_transcript=False, versions=1)
    assert verify_bundle(b.zip_bytes()).verdict == "UNCHANGED"


def test_unsupported_spec_version_is_refused_not_altered():
    b = rehash(build_bundle(), lambda body: body.update(spec_version="99.0"))
    with pytest.raises(UnsupportedSpecVersion):
        verify_bundle(b.zip_bytes())


@pytest.mark.parametrize("data", [b"", b"not a zip", b"PK\x03\x04garbage"])
def test_not_a_bundle(data):
    with pytest.raises(BundleFormatError) as err:
        verify_bundle(data)
    assert "This file is not a VeriDoc receipt bundle." in str(err.value)


def test_zip_without_receipt_is_not_a_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(BundleFormatError):
        verify_bundle(buf.getvalue())


def test_unknown_extra_files_are_a_warning():
    b = build_bundle()
    b.files["extra/notes.txt"] = b"hello"
    r = verify_bundle(b.zip_bytes())
    assert r.verdict == "UNCHANGED" and any("extra/notes.txt" in w for w in r.warnings)


def test_inconsistent_timestamps_warn_without_altering():
    # recorded_at earlier than the latest message: inconsistent order (step 6), not a chain contradiction
    b = rehash(build_bundle(), lambda body: body.update(recorded_at="2026-10-01T00:00:00+05:30"))
    r = verify_bundle(b.zip_bytes())
    assert r.verdict == "UNCHANGED"
    assert next(c for c in r.checks if c.name == "timestamps").ok is False
    assert any("inconsistent" in w for w in r.warnings)


def test_anchor_present_is_reported_but_not_checked_offline():
    anchor = {"network": "polygon-amoy", "tx": "0xabc", "block_time": "2026-10-29T12:05:00+05:30"}
    b = rehash(build_bundle(), lambda body: body.update(anchor=anchor))
    detail = next(c for c in verify_bundle(b.zip_bytes()).checks if c.name == "anchor").detail
    assert "anchored" in detail.lower() and "polygon-amoy" in detail
    assert "network" in detail.lower()  # verifying the anchor itself needs the network


def test_receipt_hash_edit_is_altered_and_named_the_receipt():
    b = build_bundle()
    env = b.json("receipt.json")
    env["receipt_hash"] = "00" * 32
    b.set_json("receipt.json", env)
    r = verify_bundle(b.zip_bytes())
    assert r.verdict == "ALTERED" and r.first_difference.kind == "receipt"
    assert next(c for c in r.checks if c.name == "spec_version").ok is False


def test_version_root_that_does_not_match_its_leaves():
    b = build_bundle()
    chain = b.json("chain.json")
    chain[1]["leaf_count"] -= 1
    b.set_json("chain.json", chain)
    r = verify_bundle(b.zip_bytes())
    assert r.verdict == "ALTERED"
    assert (r.first_difference.kind, r.first_difference.version_n) == ("chain_link", 2)
    assert next(c for c in r.checks if c.name == "version_roots").ok is False


def test_chain_json_agreeing_with_itself_but_not_with_the_receipt_is_caught():
    b = build_bundle()
    chain = b.json("chain.json")
    chain[2]["link"] = "11" * 32
    b.set_json("chain.json", chain)
    assert verify_bundle(b.zip_bytes()).first_difference.version_n == 3


def test_extra_version_in_chain_json_is_altered():
    b = build_bundle()
    chain = b.json("chain.json")
    b.set_json("chain.json", chain + [dict(chain[-1], version_n=4)])
    assert verify_bundle(b.zip_bytes()).first_difference.version_n == 4


def test_missing_import_record_is_altered():
    b = build_bundle()
    del b.files["import_record.json"]
    assert verify_bundle(b.zip_bytes()).first_difference.kind == "import_record"


def test_malformed_leaf_row_is_altered_not_a_crash():
    b = build_bundle()
    rows = b.leaves()
    rows[3]["leaf_hash"] = "not hex"
    b.set_leaves(rows)
    r = verify_bundle(b.zip_bytes())
    assert r.verdict == "ALTERED" and r.first_difference.seq == 4


def test_leaf_row_in_the_wrong_order_is_altered():
    b = build_bundle()
    rows = b.leaves()
    rows[1], rows[2] = rows[2], rows[1]
    b.set_leaves(rows)
    assert verify_bundle(b.zip_bytes()).first_difference.seq == 3


def test_command_line_summary(tmp_path, capsys):
    from packages.integrity.verify import main

    p = tmp_path / "ok.zip"
    p.write_bytes(build_bundle().zip_bytes())
    assert main([str(p)]) == 0
    assert "✓ UNCHANGED since recording" in capsys.readouterr().out
    p.write_bytes(b"nope")
    assert main([str(p)]) == 2


def test_verifier_does_not_use_the_network(block_network):
    assert verify_bundle(build_bundle().zip_bytes()).verdict == "UNCHANGED"
