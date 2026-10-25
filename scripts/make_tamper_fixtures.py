"""Write the tamper fixtures to test-vectors/integrity/tamper/ (INTEGRITY_SPEC section 11; PHASES.md Phase 7).

    uv run python scripts/make_tamper_fixtures.py           # write unchanged.zip, one zip per case, expected.json
    uv run python scripts/make_tamper_fixtures.py --check   # fail if the files differ from what the code produces

Bundles come from tests/phase_07/bundle_builder.py, which builds conforming bundles from the Phase 1 primitives
alone (the transcript case uses a synthetic 0x12 leaf: the verifier does not look inside payloads). The expected
verdicts are what the Python verifier reports; tests/phase_07/test_tamper_cases.py pins them independently.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests" / "phase_07")]

from bundle_builder import (  # noqa: E402
    Bundle,
    build_bundle,
    tamper_change_message,
    tamper_change_transcript,
    tamper_edit_version,
    tamper_import_record,
    tamper_remove_message,
    tamper_replace_audio,
    tamper_swap_messages,
    tamper_truncate_chain,
)

from packages.integrity.verify import verify_bundle  # noqa: E402

OUT = ROOT / "test-vectors" / "integrity" / "tamper"
CASES = {
    "changed_message": tamper_change_message,
    "removed_message": tamper_remove_message,
    "swapped_messages": tamper_swap_messages,
    "replaced_audio": tamper_replace_audio,
    "changed_transcript": tamper_change_transcript,
    "edited_version": tamper_edit_version,
    "truncated_chain": tamper_truncate_chain,
    "changed_import_record": tamper_import_record,
}


def stable_zip(bundle: Bundle) -> bytes:
    """The bundle as a zip with fixed timestamps, so the files do not change from run to run."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(bundle.files.items()):
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def build() -> dict[str, bytes]:
    files = {"unchanged.zip": stable_zip(build_bundle())}
    for name, tamper in CASES.items():
        files[f"{name}.zip"] = stable_zip(tamper(build_bundle()))
    expected = {}
    for name, data in files.items():
        result = verify_bundle(data)
        fd = result.first_difference
        expected[name] = {"verdict": result.verdict, "kind": fd.kind if fd else None,
                          "seq": fd.seq if fd else None, "version_n": fd.version_n if fd else None}
    files["expected.json"] = (json.dumps(expected, indent=2) + "\n").encode("utf-8")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or check the tamper fixtures")
    parser.add_argument("--check", action="store_true", help="exit 1 if a fixture differs from the code")
    args = parser.parse_args(argv)
    files = build()
    if args.check:
        stale = [n for n, data in files.items() if not (OUT / n).is_file() or (OUT / n).read_bytes() != data]
        for name in stale:
            print(f"test-vectors/integrity/tamper/{name} differs from the code")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (OUT / name).write_bytes(data)
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
