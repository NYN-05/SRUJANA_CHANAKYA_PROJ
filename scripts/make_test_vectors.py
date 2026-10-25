"""Write test-vectors/integrity/*.json from the real Python code (INTEGRITY_SPEC section 13, PHASES.md Appendix B).

    uv run python scripts/make_test_vectors.py           # write the files and the worked-example table
    uv run python scripts/make_test_vectors.py --check   # regenerate in memory; exit 1 on any difference

Values are never typed by hand. The worked-example table in DOCS/TECHNICAL.md (between the
worked-example markers) is rewritten from the same values and checked in --check mode.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.integrity.chain import chain_link, terms_digest  # noqa: E402
from packages.integrity.echo import codes_match, echo_code, recap_hash  # noqa: E402
from packages.integrity.hashing import (  # noqa: E402
    CanonicalizationError,
    TypeByte,
    canonicalize,
    leaf_hash,
    normalize_record,
    payload_digest_bytes,
    payload_digest_json,
    plain_hash,
    sha256,
)
from packages.integrity.merkle import inclusion_proof, merkle_root  # noqa: E402
from packages.integrity.receipt import SPEC_VERSION  # noqa: E402
from packages.integrity.timestamp import parse_timestamp  # noqa: E402

OUT = ROOT / "test-vectors" / "integrity"
SPEC_DOC = ROOT / "DOCS" / "TECHNICAL.md"
TABLE = re.compile(r"(<!-- worked-example:start -->\n)(.*?)(<!-- worked-example:end -->)", re.S)
TS = "2026-10-12T10:02:00+05:30"


def case(name: str, inp: dict[str, Any], expected: dict[str, Any], only: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"name": name, "input": inp, "expected": expected}
    if only:
        out["only"] = only
    return out


def group(name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"group": name, "spec_version": SPEC_VERSION, "cases": cases}


def salt(n: int) -> bytes:
    return bytes([n]) * 16


# ---- groups ----


def sha256_cases() -> list[dict[str, Any]]:
    texts = {"abc": "abc", "empty": "", "hindi": "नमस्ते", "kannada": "ಕನ್ನಡ", "rupee": "₹48,000", "long": "a" * 1000}
    return [case(n, {"utf8": t}, {"hex": sha256(t.encode("utf-8")).hex()}) for n, t in texts.items()]


JCS_INPUTS = [
    ("key_order", '{"b":1,"a":2,"c":{"z":1,"y":[3,2,1]}}'),
    ("utf16_key_order", '{"～":1,"\U0001f600":2,"a":3,"é":4}'),
    ("hindi_kannada_rupee", '{"t":"नमस्ते ಕನ್ನಡ ₹"}'),
    ("escapes", '{"a":"\\n\\t\\"\\\\/\\u001f\\b\\f\\r"}'),
    ("escaped_input_unescaped_output", '{"a":"\\u00e9\\u20b9"}'),
    ("decomposed_kept_by_jcs", '{"a":"e\\u0301"}'),
    ("number_table", "[0,-0,1.0,4.50,2e-3,1e21,1e30,1e-7,0.000001,333333333.33333329,1e-27]"),
    ("number_extremes", "[5e-324,1.7976931348623157e308,9007199254740991,-9007199254740991,0.1,100,1e20]"),
    ("literals_and_empty", '{"t":true,"f":false,"n":null,"o":{},"l":[]}'),
    ("empty_object", "{}"),
    ("empty_array", "[]"),
    ("nested_arrays", '[[],[[]],{"a":[{}]}]'),
    ("overflow_to_infinity", "[1e400]"),
]
# JavaScript cannot tell these apart after JSON.parse (or cannot parse them), so only Python checks them.
JCS_PYTHON_ONLY = [
    ("unsafe_integer_2_53", "[9007199254740992]"),
    ("unsafe_negative_integer", "[-9007199254740992]"),
    ("large_integer", '{"x":100000000000000000000}'),
    ("nan", "[NaN]"),
    ("infinity", "[Infinity]"),
]


def jcs_cases() -> list[dict[str, Any]]:
    out = []
    for only, items in ((None, JCS_INPUTS), ("python", JCS_PYTHON_ONLY)):
        for name, text in items:
            try:
                expected: dict[str, Any] = {"canonical": canonicalize(json.loads(text)).decode("utf-8")}
            except CanonicalizationError:
                expected = {"reject": True}
            out.append(case(name, {"json_text": text}, expected, only))
    return out


NORMALIZE_INPUTS = {
    "combining_acute": "é",
    "crlf": "a\r\nb",
    "lone_cr": "a\rb",
    "mixed_line_endings": "a\r\n\r\nb\rc\nd",
    "hindi_nfc": "नमस्ते",
    "hindi_nukta_composition_exclusion": "क़",
    "kannada_vowel_sign_composition": "ಕೀ",
    "spaces_not_trimmed": "  two  spaces  ",
    "record_values_not_keys": {"é": "é", "n": 5, "f": 1.5, "b": True, "z": None},
    "nested": {"list": ["a\r\nb", {"k": "é"}], "deep": {"x": ["\r"]}},
}


def normalize_cases() -> list[dict[str, Any]]:
    return [case(n, {"value": v}, {"value": normalize_record(v)}) for n, v in NORMALIZE_INPUTS.items()]


def message(seq: int, text: str) -> dict[str, Any]:
    return {
        "id": f"00000000-0000-4000-8000-{seq:012d}",
        "deal_id": "00000000-0000-4000-8000-0000000000aa",
        "seq": seq,
        "sender_id": "Raju",
        "ts": TS,
        "text": text,
        "attachment_hash": None,
        "is_system": False,
        "origin": "export",
    }


SOURCE = {"kind": "message", "message_id": message(1, "")["id"], "seq": 1, "start": 0, "end": 10, "quote": "200 shirts"}
TERM = {
    "deal_id": "d1",
    "version_n": 1,
    "key": "price",
    "value": {"kind": "money", "paise": "48000", "per": "item"},
    "sources": [SOURCE],
    "confirmed_by": "me",
    "confirmed_at": TS,
}
LEAF_INPUTS: list[tuple[str, int, dict[str, Any]]] = [
    ("message", TypeByte.MESSAGE, {"payload_json": message(1, "200 shirts, 480 each ok?")}),
    ("message_hindi_crlf", TypeByte.MESSAGE, {"payload_json": message(2, "ठीक है\r\n₹48,000 भेज दिए")}),
    ("voice_audio_raw_bytes", TypeByte.VOICE_AUDIO, {"payload_hex": b"OggS\x00\x02fake-audio".hex()}),
    (
        "transcript_span",
        TypeByte.TRANSCRIPT_SPAN,
        {
            "payload_json": {
                "transcript_id": "t1",
                "voice_note_id": "v1",
                "model": "whisper-small",
                "model_version": "1",
                "language": "hi",
                "index": 0,
                "start_ms": 12000,
                "end_ms": 18000,
                "text": "पंद्रह नवंबर तक",
            }
        },
    ),
    (
        "handshake_seal",
        TypeByte.HANDSHAKE_SEAL,
        {
            "payload_json": {
                "deal_id": "d1",
                "party_id": "p1",
                "order": 1,
                "mode": "blind",
                "answers": [{"term_key": "price", "value": {"kind": "money", "paise": "48000"}, "raw": "480"}],
                "sealed_at": TS,
            }
        },
    ),
    ("attachment_raw_bytes", TypeByte.ATTACHMENT, {"payload_hex": b"\x89PNG\r\n\x1a\n".hex()}),
    ("term", TypeByte.TERM, {"payload_json": TERM}),
    (
        "confirmation",
        TypeByte.CONFIRMATION,
        {
            "payload_json": {
                "deal_id": "d1",
                "version_n": 1,
                "party_id": "p2",
                "reply_text": "CONFIRM 7F3K",
                "reply_ts": TS,
                "code": "7F3K",
                "sender_entered_by_user": False,
            }
        },
    ),
]
LEAF_REJECTS = [
    ("salt_15_bytes", TypeByte.MESSAGE, bytes(15)),
    ("salt_17_bytes", TypeByte.MESSAGE, bytes(17)),
    ("plain_type_as_leaf", TypeByte.RECAP, salt(1)),
    ("receipt_type_as_leaf", TypeByte.RECEIPT, salt(1)),
    ("reserved_zero_type", 0x00, salt(1)),
    ("unknown_type", 0x99, salt(1)),
]


def leaf_cases() -> list[dict[str, Any]]:
    out = []
    for i, (name, type_byte, payload) in enumerate(LEAF_INPUTS, start=1):
        inp = {"type_byte": int(type_byte), "salt_hex": salt(i).hex(), **payload}
        if "payload_json" in payload:
            digest = payload_digest_json(payload["payload_json"])
        else:
            digest = payload_digest_bytes(bytes.fromhex(payload["payload_hex"]))
        out.append(case(name, inp, {"payload_digest": digest.hex(), "leaf": leaf_hash(type_byte, salt(i), digest).hex()}))
    for name, type_byte, bad_salt in LEAF_REJECTS:
        inp = {"type_byte": int(type_byte), "salt_hex": bad_salt.hex(), "payload_hex": b"payload".hex()}
        out.append(case(name, inp, {"reject": True}))
    return out


TERMS_SET = {
    "deal_id": "d1",
    "version_n": 1,
    "playbook": {"key": "supply_order", "version": 1},
    "terms": [
        {k: v for k, v in TERM.items() if k not in ("deal_id", "version_n")}
        | {"key": "delivery_date", "value": {"kind": "date", "date": "2026-11-15"}},
        {k: v for k, v in TERM.items() if k not in ("deal_id", "version_n")},
    ],
}
RECAP_EN = {
    "deal_id": "d1",
    "version_n": 1,
    "language": "en",
    "lines": [
        {"term_key": "price", "text": "200 shirts at ₹480 each = ₹96,000", "sources": ["m1"]},
        {"term_key": "advance", "text": "₹48,000 advance received", "sources": ["m4"]},
    ],
    "body_text": "Hi Meena, just confirming what we discussed:\n• 200 shirts at ₹480 each = ₹96,000\n• ₹48,000 advance received",
}
RECAP_HI = dict(
    RECAP_EN,
    language="hi",
    lines=[{"term_key": "delivery_date", "text": "डिलीवरी 15 नवंबर 2026 तक", "sources": ["m12"]}],
    body_text="नमस्ते Meena, हमारी बात का सार यह है:\n• डिलीवरी 15 नवंबर 2026 तक",
)
IMPORT_RECORD = {
    "deal_id": "d1",
    "export_digest": sha256(b"12/10/26, 10:02 - Raju: 200 shirts, 480 each ok?\n").hex(),
    "file_name": "WhatsApp Chat with Meena.txt",
    "message_count": 14,
    "imported_at": "2026-10-24T11:40:00+05:30",
}
RECEIPT_BODY = {
    "spec_version": SPEC_VERSION,
    "deal_id": "d1",
    "leaf_count": 3,
    "root": "eabcf74ed1892907946af628a5c56b54b6ef1ec1fb22746d847fd2fc19eca2a5",
    "chain": [],
    "recorded_at": "2026-10-24T11:42:00+05:30",
    "anchor": None,
    "import_record_hash": plain_hash(TypeByte.IMPORT_RECORD, IMPORT_RECORD).hex(),
}


def plain_cases() -> list[dict[str, Any]]:
    inputs: list[tuple[str, int, Any]] = [
        ("import_record", TypeByte.IMPORT_RECORD, IMPORT_RECORD),
        ("terms_set", TypeByte.TERMS_SET, TERMS_SET),
        ("recap_en", TypeByte.RECAP, RECAP_EN),
        ("recap_hi", TypeByte.RECAP, RECAP_HI),
        ("receipt_body", TypeByte.RECEIPT, RECEIPT_BODY),
    ]
    out = [case(n, {"type_byte": int(t), "object": o}, {"hash": plain_hash(t, o).hex()}) for n, t, o in inputs]
    for name, t in (("salted_type_as_plain", TypeByte.MESSAGE), ("confirmation_as_plain", TypeByte.CONFIRMATION)):
        out.append(case(name, {"type_byte": int(t), "object": {"a": 1}}, {"reject": True}))
    for name, t in (("reserved_zero_type", 0x00), ("unknown_type", 0x99)):
        out.append(case(name, {"type_byte": t, "object": {"a": 1}}, {"reject": True}))
    return out


def leaves_of(n: int) -> list[bytes]:
    return [sha256(f"leaf-{i}".encode()) for i in range(n)]


def merkle_cases() -> list[dict[str, Any]]:
    out = [case("empty_tree", {"leaves": []}, {"reject": True})]
    for n in (1, 2, 3, 4, 5, 7, 9, 16):
        leaves = leaves_of(n)
        proofs = [[{"side": s, "hash": h.hex()} for s, h in inclusion_proof(leaves, i)] for i in range(n)]
        out.append(case(f"size_{n}", {"leaves": [x.hex() for x in leaves]}, {"root": merkle_root(leaves).hex(), "proofs": proofs}))
    return out


def chain_cases() -> list[dict[str, Any]]:
    versions = []
    for n, delivery, leaf_count in ((1, "2026-11-08", 3), (2, "2026-11-15", 5), (3, "2026-11-15", 7)):
        terms_set = dict(TERMS_SET, version_n=n)
        terms_set["terms"] = [dict(TERMS_SET["terms"][0], value={"kind": "date", "date": delivery}), TERMS_SET["terms"][1]]
        versions.append({"terms_set": terms_set, "root": merkle_root(leaves_of(leaf_count)).hex()})
    digests, links, prev = [], [], None
    for v in versions:
        digest = terms_digest(v["terms_set"])
        prev = chain_link(prev, digest, bytes.fromhex(v["root"]))
        digests.append(digest.hex())
        links.append(prev.hex())
    return [case("three_versions", {"versions": versions}, {"terms_digests": digests, "links": links})]


REPLIES = [
    ("exact", "CONFIRM 7F3K", "7F3K"),
    ("lower_case", "confirm 7f3k", "7F3K"),
    ("extra_spaces", "  Confirm    7F3K  ", "7F3K"),
    ("text_around", "ok confirm 7f3k thanks", "7F3K"),
    ("trailing_newline", "CONFIRM 7F3K\n", "7F3K"),
    ("hindi_around", "ठीक है CONFIRM 7f3k", "7F3K"),
    ("o_for_zero_i_l_for_one", "CONFIRM O1LI", "0111"),
    ("lower_o_for_zero", "confirm 7o3k", "703K"),
    ("word_confirm_not_mapped", "CONFIRM ABCD", "ABCD"),
    ("wrong_code", "CONFIRM 7F3L", "7F3K"),
    ("no_code", "CONFIRM", "7F3K"),
    ("confirmed_is_not_confirm", "CONFIRMED 7F3K", "7F3K"),
    ("code_without_confirm", "ok 7F3K", "7F3K"),
    ("empty", "", "7F3K"),
    ("letter_u_not_in_alphabet", "CONFIRM 7F3U", "7F3V"),
    ("code_too_long", "CONFIRM 7F3KX", "7F3K"),
]


def echo_cases() -> list[dict[str, Any]]:
    out = []
    recaps = {"recap_en": RECAP_EN, "recap_hi": RECAP_HI, "recap_one_char_changed": dict(RECAP_EN, body_text=RECAP_EN["body_text"] + ".")}
    for name, recap in recaps.items():
        digest = recap_hash(recap)
        out.append(case(name, {"recap": recap}, {"recap_hash": digest.hex(), "code": echo_code(digest)}))
    for name, reply, code in REPLIES:
        out.append(case(name, {"reply": reply, "code": code}, {"match": codes_match(reply, code)}))
    return out


TIMESTAMPS = [
    "2026-10-12T10:02:00+05:30",
    "2026-10-12T04:32:00+00:00",
    "2026-01-02T03:04:05-03:30",
    "2028-02-29T00:00:00+05:30",
    "2026-12-31T23:59:59+14:00",
    "2026-10-12T10:02:00Z",
    "2026-10-12T10:02:00",
    "2026-10-12T10:02:00.000+05:30",
    "2026-10-12T10:02:00-00:00",
    "2026-02-30T10:02:00+05:30",
    "2027-02-29T10:02:00+05:30",
    "2026-13-01T10:02:00+05:30",
    "2026-10-12T24:00:00+05:30",
    "2026-10-12T10:60:00+05:30",
    "2026-10-12T10:02:60+05:30",
    "2026-10-12T10:02:00+25:00",
    "2026-10-12T10:02:00+05:60",
    "2026-10-12T10:02+05:30",
    "2026-10-12 10:02:00+05:30",
    "20261012T100200+0530",
    "",
]


def timestamp_cases() -> list[dict[str, Any]]:
    out = []
    for text in TIMESTAMPS:
        try:
            parse_timestamp(text)
            valid = True
        except ValueError:
            valid = False
        out.append(case(text or "empty", {"text": text}, {"valid": valid}))
    return out


WORKED_PAYLOADS = [
    {"id": 1, "sender": "Asha", "text": "50 mugs, 120 each ok?", "ts": "2026-10-12T10:02:00+05:30"},
    {"id": 2, "sender": "Bilal", "text": "ok. delivery next week", "ts": "2026-10-12T10:04:00+05:30"},
    {"id": 3, "sender": "Asha", "text": "advance half now", "ts": "2026-10-12T10:05:00+05:30"},
]


def worked_example() -> dict[str, Any]:
    leaves = [leaf_hash(TypeByte.MESSAGE, salt(i), payload_digest_json(p)) for i, p in enumerate(WORKED_PAYLOADS, start=1)]
    expected = {
        "payload_1_jcs": canonicalize(WORKED_PAYLOADS[0]).decode("utf-8"),
        "leaves": [x.hex() for x in leaves],
        "node_1_2": merkle_root(leaves[:2]).hex(),
        "root": merkle_root(leaves).hex(),
    }
    inp = {"type_byte": int(TypeByte.MESSAGE), "payloads": WORKED_PAYLOADS, "salts_hex": [salt(i).hex() for i in (1, 2, 3)]}
    return case("integrity_spec_section_6", inp, expected)


def worked_table(expected: dict[str, Any]) -> str:
    leaves = expected["leaves"]
    rows = [
        ("Payload 1 (JCS)", expected["payload_1_jcs"]),
        ("Leaf 1", leaves[0]),
        ("Leaf 2", leaves[1]),
        ("Leaf 3", leaves[2]),
        ("Node(1,2)", expected["node_1_2"]),
        ("Root (node(1,2) with leaf 3 carried up)", expected["root"]),
    ]
    return "| Item | Value |\n|---|---|\n" + "".join(f"| {k} | `{v}` |\n" for k, v in rows)


def build() -> tuple[dict[str, str], str]:
    """The vector files (name to text) and the worked-example table for the spec."""
    worked = worked_example()
    groups = {
        "sha256.json": group("sha256", sha256_cases()),
        "jcs.json": group("jcs", jcs_cases()),
        "normalize.json": group("normalize", normalize_cases()),
        "leaves.json": group("leaves", leaf_cases()),
        "plain.json": group("plain", plain_cases()),
        "merkle.json": group("merkle", merkle_cases()),
        "chain.json": group("chain", chain_cases()),
        "echo.json": group("echo", echo_cases()),
        "timestamp.json": group("timestamp", timestamp_cases()),
        "worked_example.json": group("worked_example", [worked]),
    }
    # ASCII escapes keep decomposed and composed forms distinct whatever an editor does to the file.
    files = {name: json.dumps(data, indent=2, ensure_ascii=True) + "\n" for name, data in groups.items()}
    return files, worked_table(worked["expected"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or check test-vectors/integrity/*.json")
    parser.add_argument("--check", action="store_true", help="fail if any file or the spec table differs")
    args = parser.parse_args(argv)
    files, table = build()
    doc = SPEC_DOC.read_text(encoding="utf-8") if SPEC_DOC.is_file() else None
    match = TABLE.search(doc) if doc else None
    problems = []
    if doc is not None and not match:
        problems.append(f"{SPEC_DOC.relative_to(ROOT)}: worked-example markers not found")
    if args.check:
        for name, text in files.items():
            path = OUT / name
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                problems.append(f"{path.relative_to(ROOT)} differs from the code")
        if match and match.group(2) != table:
            problems.append(f"{SPEC_DOC.relative_to(ROOT)}: worked-example table differs from the vectors")
        for problem in problems:
            print(problem)
        if not problems:
            print(f"{len(files)} vector files and the worked-example table match the code")
        return 1 if problems else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    if match and doc is not None:
        SPEC_DOC.write_text(doc[: match.start(2)] + table + doc[match.end(2) :], encoding="utf-8", newline="\n")
    for problem in problems:
        print(problem)
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
