"""Verify a receipt bundle offline (INTEGRITY_SPEC section 10; PHASES.md Appendix D; I-09, I-21).

Pure: reads one zip, uses the Phase 1 primitives, writes nothing and never touches the network. It never
repairs anything: any mismatch is ALTERED. Leaves are rebuilt from their *recomputed* hashes, so a leaf edited
together with its listed hash still breaks the root.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from packages.contracts import FirstDifference, VerifyCheck, VerifyResult
from packages.integrity.chain import chain_link, terms_digest
from packages.integrity.hashing import CanonicalizationError, TypeByte, leaf_hash, payload_digest_bytes, payload_digest_json, plain_hash
from packages.integrity.merkle import merkle_root
from packages.integrity.receipt import SPEC_VERSION, receipt_hash
from packages.integrity.timestamp import parse_timestamp

NOT_A_BUNDLE = "This file is not a VeriDoc receipt bundle."
SUPPORTED_SPEC_VERSIONS = {SPEC_VERSION}
KNOWN_MEMBERS = {"receipt.json", "leaves.jsonl", "chain.json", "import_record.json", "README.txt"}
KINDS = {"message", "voice_audio", "transcript_span", "handshake_seal", "attachment", "term", "confirmation"}
MAX_BUNDLE_BYTES = 1 << 30


class BundleFormatError(ValueError):
    """The file is not a readable VeriDoc receipt bundle."""


class UnsupportedSpecVersion(ValueError):
    """The receipt was made under a spec version this verifier does not know. It is refused, not called ALTERED."""


def _read_zip(source: bytes | str | Path) -> dict[str, bytes]:
    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else bytes(source)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_BUNDLE_BYTES:
                raise BundleFormatError(NOT_A_BUNDLE)
            return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    except (zipfile.BadZipFile, EOFError, NotImplementedError, RuntimeError, OSError, ValueError) as exc:
        if isinstance(exc, BundleFormatError):
            raise
        raise BundleFormatError(NOT_A_BUNDLE) from exc


def _check_leaf(row: dict[str, Any], files: dict[str, bytes]) -> tuple[bytes, bool]:
    """(the leaf hash recomputed from what the bundle discloses, whether the row is consistent)."""
    try:
        listed = bytes.fromhex(row["leaf_hash"])
    except (KeyError, ValueError, TypeError):
        return bytes(32), False
    try:
        salt = bytes.fromhex(row["salt"]) if row.get("salt") else None
        digest = bytes.fromhex(row["payload_digest"]) if row.get("payload_digest") else None
        if row.get("payload") is not None:
            calc = payload_digest_json(row["payload"])
        elif row.get("payload_file") and row["payload_file"] in files:
            calc = payload_digest_bytes(files[row["payload_file"]])
        else:
            calc = digest  # nothing disclosed to recompute from: taken as given
        ok = digest is None or calc == digest
        use = calc if calc is not None else digest
        if salt is None or use is None:
            return listed, ok
        recomputed = leaf_hash(row["type_byte"], salt, use)
        return recomputed, ok and recomputed == listed
    except (KeyError, ValueError, TypeError, CanonicalizationError):
        return listed, False


def _difference(kind: str, seq: Any = None, version_n: Any = None) -> FirstDifference:
    return FirstDifference(
        kind=kind,  # type: ignore[arg-type]
        seq=seq if isinstance(seq, int) and seq >= 1 else None,
        version_n=version_n if isinstance(version_n, int) and version_n >= 1 else None,
    )


def verify_bundle(source: bytes | str | Path) -> VerifyResult:
    """Verdict ``UNCHANGED`` or ``ALTERED`` with the first differing item. Raises BundleFormatError for a file that is
    not a bundle and UnsupportedSpecVersion for a spec version it does not know."""
    files = _read_zip(source)
    try:
        envelope = json.loads(files["receipt.json"])
        body, claimed = envelope["body"], envelope["receipt_hash"]
        rows = [json.loads(line) for line in files["leaves.jsonl"].decode("utf-8").split("\n") if line.strip()]
        chain_json = json.loads(files["chain.json"]) if "chain.json" in files else []
        record = json.loads(files["import_record.json"]) if "import_record.json" in files else None
        spec = body["spec_version"]
        body_chain = body.get("chain", [])
        if not (isinstance(body, dict) and isinstance(rows, list) and all(isinstance(r, dict) for r in rows) and isinstance(chain_json, list)):
            raise TypeError
    except (KeyError, ValueError, TypeError, UnicodeDecodeError, AttributeError) as exc:
        raise BundleFormatError(NOT_A_BUNDLE) from exc
    if spec not in SUPPORTED_SPEC_VERSIONS:
        raise UnsupportedSpecVersion(f"spec version {spec!r} is not supported")

    checks: list[VerifyCheck] = []
    warnings = [f"unknown file ignored: {n}" for n in files if n not in KNOWN_MEMBERS and not n.startswith("media/")]
    candidates: dict[str, FirstDifference] = {}

    # the envelope: the receipt hash covers the body only
    try:
        envelope_ok = receipt_hash(body).hex() == claimed
    except (CanonicalizationError, ValueError, TypeError):
        envelope_ok = False
    checks.append(VerifyCheck(name="spec_version", ok=envelope_ok, detail=f"spec {spec}; " + ("receipt hash matches" if envelope_ok else "receipt hash does not match its body")))
    if not envelope_ok:
        candidates["receipt"] = _difference("receipt")

    # leaves: each one recomputed; the first failure in order names the item
    recomputed, leaf_bad = [], None
    for index, row in enumerate(rows):
        leaf, ok = _check_leaf(row, files)
        recomputed.append(leaf)
        if (not ok or row.get("seq") != index + 1) and leaf_bad is None:
            leaf_bad = row
    if leaf_bad is not None:
        kind = leaf_bad.get("kind") if leaf_bad.get("kind") in KINDS else "message"
        candidates["leaf"] = _difference(kind, leaf_bad.get("seq"))
    checks.append(VerifyCheck(
        name="leaves", ok=leaf_bad is None,
        detail=f"{len(rows)} leaves checked" if leaf_bad is None else f"leaf {leaf_bad.get('seq')} ({leaf_bad.get('kind')}) does not match",
    ))

    # the Merkle root, rebuilt from the recomputed leaf hashes
    try:
        root_ok = bool(rows) and merkle_root(recomputed).hex() == body["root"] and body["leaf_count"] == len(rows)
    except (KeyError, ValueError, TypeError):
        root_ok = False
    checks.append(VerifyCheck(name="merkle_root", ok=root_ok, detail="root matches" if root_ok else "root does not match the leaves"))
    if not root_ok:
        candidates["root"] = _difference("root")

    # the version chain: digests and links recomputed, then compared with chain.json and the receipt body
    by_version = {e.get("version_n"): e for e in chain_json if isinstance(e, dict)}
    chain_bad, roots_bad, good, previous = [], [], 0, None
    for entry in body_chain:
        version = entry.get("version_n") if isinstance(entry, dict) else None
        full = by_version.get(version)
        chain_ok = roots_ok = False
        if full is not None:
            try:
                digest = terms_digest(full["terms_set"])
                link = chain_link(previous, digest, bytes.fromhex(full["root"]))
                chain_ok = (digest.hex() == full["terms_digest"] == entry["terms_digest"] and link.hex() == full["link"] == entry["link"]
                            and full["root"] == entry["root"])
                previous = link
                count = full["leaf_count"]
                roots_ok = isinstance(count, int) and 1 <= count <= len(recomputed) and merkle_root(recomputed[:count]).hex() == full["root"]
            except (KeyError, ValueError, TypeError, CanonicalizationError):
                pass
        good += chain_ok
        if not chain_ok:
            chain_bad.append(version)
        if not roots_ok:
            roots_bad.append(version)
    chain_bad += [v for v in by_version if v not in {e.get("version_n") for e in body_chain if isinstance(e, dict)}]
    checks.append(VerifyCheck(name="chain", ok=not chain_bad, detail=f"{good} of {len(body_chain)} links verified" if body_chain else "no versions yet"))
    checks.append(VerifyCheck(name="version_roots", ok=not roots_bad, detail="every version root matches its leaves" if not roots_bad else f"version {min(roots_bad, key=str)} root does not match"))
    if chain_bad:
        candidates["chain"] = _difference("chain_link", None, min((v for v in chain_bad if isinstance(v, int)), default=None))
    if roots_bad:
        candidates["version_roots"] = _difference("chain_link", None, min((v for v in roots_bad if isinstance(v, int)), default=None))

    # the import record (I-09)
    try:
        record_ok = record is not None and plain_hash(TypeByte.IMPORT_RECORD, record).hex() == body["import_record_hash"]
    except (KeyError, ValueError, TypeError, CanonicalizationError):
        record_ok = False
    checks.append(VerifyCheck(name="import_record", ok=record_ok, detail="import record matches" if record_ok else "import record does not match the receipt"))
    if not record_ok:
        candidates["import_record"] = _difference("import_record")

    # timestamps: an inconsistent order is a warning, never ALTERED on its own (step 6)
    stamps = [r["payload"]["ts"] for r in rows if r.get("kind") == "message" and isinstance(r.get("payload"), dict) and "ts" in r["payload"]]
    stamps += [e["created_at"] for e in chain_json if isinstance(e, dict) and "created_at" in e]
    try:
        recorded = parse_timestamp(body["recorded_at"])
        times = [parse_timestamp(s) for s in stamps]
        created = [parse_timestamp(e["created_at"]) for e in chain_json if isinstance(e, dict) and "created_at" in e]
        time_ok = all(t <= recorded for t in times) and created == sorted(created)
    except (KeyError, ValueError, TypeError):
        time_ok = False
    checks.append(VerifyCheck(name="timestamps", ok=time_ok, detail="times are in a consistent order" if time_ok else "times are inconsistent"))
    if not time_ok:
        warnings.append("timestamps are inconsistent: the receipt time is earlier than a message or versions are out of order")

    anchor = body.get("anchor")
    anchor_detail = ("not anchored: the time comes from the device clock" if anchor is None else
                     f"anchored on {anchor.get('network')} ({anchor.get('tx')}); checking the anchor itself needs the network and is not done offline")
    checks.append(VerifyCheck(name="anchor", ok=True, detail=anchor_detail))

    first = next((candidates[k] for k in ("leaf", "chain", "version_roots", "import_record", "root", "receipt") if k in candidates), None)
    return VerifyResult(verdict="ALTERED" if first else "UNCHANGED", checks=checks, first_difference=first, warnings=warnings)


def main(argv: list[str]) -> int:
    """``python -m packages.integrity.verify <bundle.zip>``: print the checks and the verdict."""
    if len(argv) != 1:
        print("usage: python -m packages.integrity.verify <bundle.zip>")
        return 2
    try:
        result = verify_bundle(argv[0])
    except (BundleFormatError, UnsupportedSpecVersion, OSError) as exc:
        print(exc)
        return 2
    for check in result.checks:
        print(f"{'✓' if check.ok else '⚠'} {check.name}: {check.detail}")
    for warning in result.warnings:
        print(f"note: {warning}")
    fd = result.first_difference
    print("✓ UNCHANGED since recording" if fd is None else f"⚠ ALTERED after recording: first difference {fd.kind} seq={fd.seq} version={fd.version_n}")
    return 0 if fd is None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
