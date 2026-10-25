"""Build and tamper receipt bundles for the Phase 7 tests (format: PHASES.md Appendix D).

Bundles are built from the Phase 1 primitives only, so the verifiers can be
tested independently of the vault. The vault's own bundles (export_bundle)
must use exactly the same format; test_bundle.py checks that.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field

from packages.integrity.chain import chain_link, terms_digest
from packages.integrity.hashing import (
    TypeByte,
    leaf_hash,
    payload_digest_bytes,
    payload_digest_json,
    plain_hash,
)
from packages.integrity.merkle import merkle_root
from packages.integrity.receipt import SPEC_VERSION, receipt_hash

KIND = {
    TypeByte.MESSAGE: "message",
    TypeByte.VOICE_AUDIO: "voice_audio",
    TypeByte.TRANSCRIPT_SPAN: "transcript_span",
    TypeByte.HANDSHAKE_SEAL: "handshake_seal",
    TypeByte.ATTACHMENT: "attachment",
    TypeByte.TERM: "term",
    TypeByte.CONFIRMATION: "confirmation",
}
DEAL = "00000000-0000-4000-8000-0000000000dd"


def message_payload(seq: int, sender: str, text: str, minute: int) -> dict:
    return {
        "id": f"00000000-0000-4000-8000-{seq:012d}",
        "deal_id": DEAL,
        "seq": seq,
        "sender_id": sender,
        "ts": f"2026-10-12T10:{minute:02d}:00+05:30",
        "text": text,
        "attachment_hash": None,
        "is_system": False,
        "origin": "export",
    }


@dataclass
class Bundle:
    files: dict[str, bytes] = field(default_factory=dict)

    # --- reading and writing members -------------------------------------
    def json(self, name):
        return json.loads(self.files[name])

    def set_json(self, name, obj):
        self.files[name] = json.dumps(obj, ensure_ascii=False).encode("utf-8")

    def leaves(self):
        return [json.loads(line) for line in self.files["leaves.jsonl"].decode("utf-8").splitlines() if line]

    def set_leaves(self, rows):
        self.files["leaves.jsonl"] = ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8")

    def zip_bytes(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in self.files.items():
                z.writestr(name, data)
        return buf.getvalue()

    @classmethod
    def from_zip(cls, data: bytes) -> "Bundle":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return cls({n: z.read(n) for n in z.namelist()})


def build_bundle(n_messages: int = 8, with_audio: bool = True, with_transcript: bool = True, versions: int = 3) -> Bundle:
    """A valid bundle: n messages, optional audio and transcript span, then `versions` versions with term leaves."""
    rows, media, seq = [], {}, 0
    salt = lambda s: bytes([s % 256]) * 16  # noqa: E731  (deterministic test salts)

    def add_json(type_byte, payload):
        nonlocal seq
        seq += 1
        digest = payload_digest_json(payload)
        rows.append({
            "seq": seq,
            "type_byte": int(type_byte),
            "kind": KIND[type_byte],
            "leaf_hash": leaf_hash(type_byte, salt(seq), digest).hex(),
            "salt": salt(seq).hex(),
            "payload_digest": digest.hex(),
            "payload": payload,
            "payload_file": None,
        })

    def add_bytes(type_byte, data):
        nonlocal seq
        seq += 1
        digest = payload_digest_bytes(data)
        media[f"media/{digest.hex()}"] = data
        rows.append({
            "seq": seq,
            "type_byte": int(type_byte),
            "kind": KIND[type_byte],
            "leaf_hash": leaf_hash(type_byte, salt(seq), digest).hex(),
            "salt": salt(seq).hex(),
            "payload_digest": digest.hex(),
            "payload": None,
            "payload_file": f"media/{digest.hex()}",
        })

    for i in range(1, n_messages + 1):
        add_json(TypeByte.MESSAGE, message_payload(i, "Raju" if i % 2 else "Meena", f"message {i} about 200 shirts", i))
    audio_note_id = "00000000-0000-4000-8000-0000000000a1"
    if with_audio:
        add_bytes(TypeByte.VOICE_AUDIO, b"OggS" + bytes(range(256)) * 4)
    if with_transcript:
        add_json(TypeByte.TRANSCRIPT_SPAN, {
            "transcript_id": "00000000-0000-4000-8000-0000000000b1",
            "voice_note_id": audio_note_id,
            "model": "faster-whisper-small",
            "model_version": "test",
            "language": "hi",
            "index": 0,
            "start_ms": 12000,
            "end_ms": 18000,
            "text": "bees November tak delivery",
        })

    chain, body_chain, prev = [], [], None
    for v in range(1, versions + 1):
        term = {"key": "delivery_date", "value": {"kind": "date", "date": f"2026-11-{7 + v:02d}"}, "sources": [], "confirmed_by": "me", "confirmed_at": f"2026-10-2{v}T10:00:00+05:30"}
        add_json(TypeByte.TERM, dict(term, deal_id=DEAL, version_n=v))
        ts = {"deal_id": DEAL, "version_n": v, "playbook": {"key": "supply_order", "version": 1}, "terms": [term]}
        td = terms_digest(ts)
        root = merkle_root([bytes.fromhex(r["leaf_hash"]) for r in rows])
        link = chain_link(prev, td, root)
        prev = link
        chain.append({"version_n": v, "terms_set": ts, "terms_digest": td.hex(), "root": root.hex(), "link": link.hex(), "leaf_count": len(rows), "created_at": f"2026-10-2{v}T10:00:00+05:30"})
        body_chain.append({"version_n": v, "terms_digest": td.hex(), "root": root.hex(), "link": link.hex()})

    import_record = {"deal_id": DEAL, "export_digest": "ab" * 32, "file_name": "chat.txt", "message_count": n_messages, "imported_at": "2026-10-12T10:59:00+05:30"}
    body = {
        "spec_version": SPEC_VERSION,
        "deal_id": DEAL,
        "leaf_count": len(rows),
        "root": merkle_root([bytes.fromhex(r["leaf_hash"]) for r in rows]).hex(),
        "chain": body_chain,
        "recorded_at": "2026-10-29T12:00:00+05:30",
        "anchor": None,
        "import_record_hash": plain_hash(TypeByte.IMPORT_RECORD, import_record).hex(),
    }
    b = Bundle()
    b.set_json("receipt.json", {"body": body, "receipt_hash": receipt_hash(body).hex()})
    b.set_leaves(rows)
    b.set_json("chain.json", chain)
    b.set_json("import_record.json", import_record)
    b.files["README.txt"] = (
        "How to verify: open verify.html and drop this file.\n"
        "This checks that the record was not changed after it was saved. "
        "It cannot prove that the original chat export was genuine.\n"
    ).encode("utf-8")
    b.files.update(media)
    return b


# --- the seven tamper cases of INTEGRITY_SPEC section 11 (+ import record) ---


def tamper_change_message(b: Bundle, seq: int = 7) -> Bundle:
    rows = b.leaves()
    row = next(r for r in rows if r["seq"] == seq)
    row["payload"]["text"] = row["payload"]["text"][:-1] + ("X" if row["payload"]["text"][-1] != "X" else "Y")
    b.set_leaves(rows)
    return b


def tamper_remove_message(b: Bundle, seq: int = 4) -> Bundle:
    b.set_leaves([r for r in b.leaves() if r["seq"] != seq])
    return b


def tamper_swap_messages(b: Bundle, a: int = 3, c: int = 5) -> Bundle:
    rows = b.leaves()
    ra = next(r for r in rows if r["seq"] == a)
    rc = next(r for r in rows if r["seq"] == c)
    ra["payload"]["text"], rc["payload"]["text"] = rc["payload"]["text"], ra["payload"]["text"]
    b.set_leaves(rows)
    return b


def tamper_replace_audio(b: Bundle) -> Bundle:
    name = next(n for n in b.files if n.startswith("media/"))
    b.files[name] = b"OggS" + b"\x00" * 1024
    return b


def tamper_change_transcript(b: Bundle) -> Bundle:
    rows = b.leaves()
    row = next(r for r in rows if r["kind"] == "transcript_span")
    row["payload"]["text"] = "pandrah November tak delivery"
    b.set_leaves(rows)
    return b


def tamper_edit_version(b: Bundle, version_n: int = 1) -> Bundle:
    chain = b.json("chain.json")
    entry = next(e for e in chain if e["version_n"] == version_n)
    entry["terms_set"]["terms"][0]["value"]["date"] = "2026-12-31"
    b.set_json("chain.json", chain)
    return b


def tamper_truncate_chain(b: Bundle) -> Bundle:
    chain = b.json("chain.json")
    b.set_json("chain.json", chain[:-1])
    return b


def tamper_import_record(b: Bundle) -> Bundle:
    rec = b.json("import_record.json")
    rec["message_count"] += 1
    b.set_json("import_record.json", rec)
    return b
