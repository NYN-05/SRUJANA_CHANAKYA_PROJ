"""llama.cpp adapter: an existing open instruction model, on the CPU, temperature 0, output limited by a JSON-schema
grammar (ADR-008). It needs the optional ``model`` extra (``llama-cpp-python``) and a GGUF file whose hash matches
``models/manifest.json``; the caller checks the hash first (``models.verify_model_file``). No network, no tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LlamaCppRunner:
    def __init__(self, model_path: str | Path, *, n_ctx: int = 4096, n_threads: int | None = None) -> None:
        from llama_cpp import Llama  # imported here so the rest of the product works without the extra

        self._llm = Llama(model_path=str(model_path), n_ctx=n_ctx, n_threads=n_threads, verbose=False)

    def generate(self, system: str, data_block: str, schema: dict[str, Any], timeout_s: float) -> str:
        """The time budget is enforced by the caller (``refine_terms``); a runner cannot be interrupted midway."""
        from llama_cpp import LlamaGrammar

        reply = self._llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": data_block}],
            grammar=LlamaGrammar.from_json_schema(json.dumps(schema)),
            temperature=0.0,
            max_tokens=1024,
        )
        return str(reply["choices"][0]["message"]["content"])
