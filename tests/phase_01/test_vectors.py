"""Phase 1: cross-language test vectors (INTEGRITY_SPEC section 13, PHASES.md Appendix B)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from packages.integrity.chain import chain_link, terms_digest
from packages.integrity.echo import codes_match, echo_code, recap_hash
from packages.integrity.hashing import (
    CanonicalizationError,
    canonicalize,
    leaf_hash,
    normalize_record,
    payload_digest_bytes,
    payload_digest_json,
    plain_hash,
    sha256,
)
from packages.integrity.merkle import EmptyTreeError, inclusion_proof, merkle_root
from packages.integrity.timestamp import parse_timestamp

ROOT = Path(__file__).resolve().parents[2]
VEC = ROOT / "test-vectors" / "integrity"
FILES = [
    "sha256.json",
    "jcs.json",
    "normalize.json",
    "leaves.json",
    "plain.json",
    "merkle.json",
    "chain.json",
    "echo.json",
    "timestamp.json",
    "worked_example.json",
]
REQUIRED_MERKLE_SIZES = {0, 1, 2, 3, 4, 5, 7, 9, 16}


def load(name: str) -> dict:
    return json.loads((VEC / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", FILES)
def test_vector_file_shape(name):
    data = load(name)
    assert set(data) >= {"group", "spec_version", "cases"}
    assert data["cases"], f"{name} has no cases"
    for case in data["cases"]:
        assert set(case) >= {"name", "input", "expected"}


def test_sha256_vectors():
    for case in load("sha256.json")["cases"]:
        assert sha256(case["input"]["utf8"].encode("utf-8")).hex() == case["expected"]["hex"], case["name"]


def test_jcs_vectors():
    cases = load("jcs.json")["cases"]
    assert any(c["expected"].get("reject") for c in cases), "jcs vectors must include rejected inputs"
    for case in cases:
        obj = json.loads(case["input"]["json_text"])
        if case["expected"].get("reject"):
            with pytest.raises(CanonicalizationError):
                canonicalize(obj)
        else:
            assert canonicalize(obj).decode("utf-8") == case["expected"]["canonical"], case["name"]


def test_normalize_vectors():
    for case in load("normalize.json")["cases"]:
        assert normalize_record(case["input"]["value"]) == case["expected"]["value"], case["name"]


def test_leaf_vectors_cover_every_salted_type():
    cases = load("leaves.json")["cases"]
    seen = set()
    for case in cases:
        inp, exp = case["input"], case["expected"]
        salt = bytes.fromhex(inp["salt_hex"])
        if exp.get("reject"):
            with pytest.raises(ValueError):
                digest = payload_digest_bytes(bytes.fromhex(inp.get("payload_hex", "")))
                leaf_hash(inp["type_byte"], salt, digest)
            continue
        if "payload_json" in inp:
            digest = payload_digest_json(inp["payload_json"])
        else:
            digest = payload_digest_bytes(bytes.fromhex(inp["payload_hex"]))
        assert digest.hex() == exp["payload_digest"], case["name"]
        assert leaf_hash(inp["type_byte"], salt, digest).hex() == exp["leaf"], case["name"]
        seen.add(inp["type_byte"])
    assert seen >= {0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x22}


def test_plain_vectors():
    seen = set()
    for case in load("plain.json")["cases"]:
        inp, exp = case["input"], case["expected"]
        if exp.get("reject"):
            with pytest.raises(ValueError):
                plain_hash(inp["type_byte"], inp["object"])
            continue
        assert plain_hash(inp["type_byte"], inp["object"]).hex() == exp["hash"], case["name"]
        seen.add(inp["type_byte"])
    assert seen >= {0x16, 0x20, 0x21, 0x40}


def test_merkle_vectors():
    sizes = set()
    for case in load("merkle.json")["cases"]:
        leaves = [bytes.fromhex(x) for x in case["input"]["leaves"]]
        sizes.add(len(leaves))
        if case["expected"].get("reject"):
            with pytest.raises(EmptyTreeError):
                merkle_root(leaves)
            continue
        assert merkle_root(leaves).hex() == case["expected"]["root"], case["name"]
        for i, proof in enumerate(case["expected"]["proofs"]):
            got = [{"side": s, "hash": h.hex()} for s, h in inclusion_proof(leaves, i)]
            assert got == proof, f"{case['name']} proof {i}"
    assert sizes >= REQUIRED_MERKLE_SIZES


def test_chain_vectors():
    for case in load("chain.json")["cases"]:
        prev = None
        versions = case["input"]["versions"]
        assert len(versions) >= 3
        for i, v in enumerate(versions):
            td = terms_digest(v["terms_set"])
            assert td.hex() == case["expected"]["terms_digests"][i]
            prev = chain_link(prev, td, bytes.fromhex(v["root"]))
            assert prev.hex() == case["expected"]["links"][i]


def test_echo_vectors():
    has_reply_cases = False
    for case in load("echo.json")["cases"]:
        inp, exp = case["input"], case["expected"]
        if "recap" in inp:
            rh = recap_hash(inp["recap"])
            assert rh.hex() == exp["recap_hash"], case["name"]
            assert echo_code(rh) == exp["code"], case["name"]
        else:
            has_reply_cases = True
            assert codes_match(inp["reply"], inp["code"]) is exp["match"], case["name"]
    assert has_reply_cases


def test_timestamp_vectors():
    for case in load("timestamp.json")["cases"]:
        text = case["input"]["text"]
        if case["expected"]["valid"]:
            parse_timestamp(text)
        else:
            with pytest.raises(ValueError):
                parse_timestamp(text)


def test_worked_example_vector_matches_spec_table():
    data = load("worked_example.json")
    flat = json.dumps(data)
    for value in (
        "eeb767408a78a214391a6ac1741af71f760942fc6a622ac339f71ea353b1a031",
        "eabcf74ed1892907946af628a5c56b54b6ef1ec1fb22746d847fd2fc19eca2a5",
    ):
        assert value in flat


def test_generator_check_mode_passes():
    script = ROOT / "scripts" / "make_test_vectors.py"
    assert script.is_file(), "scripts/make_test_vectors.py is required"
    out = subprocess.run([sys.executable, str(script), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_generator_check_detects_a_changed_vector_file(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_test_vectors", ROOT / "scripts" / "make_test_vectors.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    out = tmp_path / "vectors"
    doc = tmp_path / "TECHNICAL.md"
    doc.write_text("x\n<!-- worked-example:start -->\nold\n<!-- worked-example:end -->\ny\n", encoding="utf-8")
    monkeypatch.setattr(gen, "OUT", out)
    monkeypatch.setattr(gen, "SPEC_DOC", doc)
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    assert gen.main([]) == 0
    assert "eabcf74ed1892907946af628a5c56b54b6ef1ec1fb22746d847fd2fc19eca2a5" in doc.read_text(encoding="utf-8")
    assert gen.main(["--check"]) == 0
    path = out / "merkle.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"left"', '"right"', 1), encoding="utf-8")
    assert gen.main(["--check"]) == 1
    gen.main([])
    doc.write_text(doc.read_text(encoding="utf-8").replace("eabcf74e", "00000000"), encoding="utf-8")
    assert gen.main(["--check"]) == 1


def test_spec_table_matches_worked_example_vector():
    import re

    doc = (ROOT / "DOCS" / "TECHNICAL.md").read_text(encoding="utf-8")
    table = re.search(r"<!-- worked-example:start -->\n(.*?)<!-- worked-example:end -->", doc, re.S).group(1)
    expected = load("worked_example.json")["cases"][0]["expected"]
    for value in [*expected["leaves"], expected["node_1_2"], expected["root"]]:
        assert value in table


def test_vectors_carry_the_current_spec_version():
    from packages.integrity.receipt import SPEC_VERSION

    assert {load(name)["spec_version"] for name in FILES} == {SPEC_VERSION}
