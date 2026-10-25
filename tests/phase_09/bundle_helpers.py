"""Small bundle edits for the end-to-end tests (format: PHASES.md Appendix D)."""

from __future__ import annotations

import io
import json
import zipfile


def change_one_char_in_message(bundle: bytes, seq: int) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(bundle))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "leaves.jsonl":
                rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
                row = next(r for r in rows if r["seq"] == seq)
                text = row["payload"]["text"]
                row["payload"]["text"] = text[:-1] + ("X" if not text.endswith("X") else "Y")
                data = ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8")
            dst.writestr(name, data)
    return out.getvalue()
