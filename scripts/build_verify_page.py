"""Build apps/verify/verify.html from the tested modules (PHASES.md I-22, ADR-015).

    uv run python scripts/build_verify_page.py           # write the page and print its SHA-256
    uv run python scripts/build_verify_page.py --check   # fail if the page is stale

The page is one file: integrity.mjs and verify.mjs are inlined into verify.template.html with their import and
export keywords removed. Publish the printed SHA-256 in the release notes (T19).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "apps" / "verify"
PAGE = VERIFY / "verify.html"
MODULES = ("integrity.mjs", "verify.mjs")


def inline(source: str) -> str:
    """A module as plain script text: no import lines, no export keywords."""
    kept = [line for line in source.splitlines() if not line.startswith("import ")]
    return re.sub(r"^export ", "", "\n".join(kept), flags=re.MULTILINE)


def build() -> str:
    code = "\n".join(inline((VERIFY / name).read_text(encoding="utf-8")) for name in MODULES)
    template = (VERIFY / "verify.template.html").read_text(encoding="utf-8")
    if "/*@code*/" not in template:
        raise SystemExit("verify.template.html has no /*@code*/ marker")
    return template.replace("/*@code*/", code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or check apps/verify/verify.html")
    parser.add_argument("--check", action="store_true", help="exit 1 if verify.html differs from the modules")
    args = parser.parse_args(argv)
    html = build()
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if args.check:
        current = PAGE.read_text(encoding="utf-8") if PAGE.is_file() else None
        if current != html:
            print("apps/verify/verify.html is stale: run scripts/build_verify_page.py")
            return 1
        print(f"verify.html is up to date (sha256 {digest})")
        return 0
    PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote apps/verify/verify.html (sha256 {digest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
