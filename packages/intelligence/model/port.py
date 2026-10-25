"""The model port: one call that returns text. Nothing else about a model is known to the rest of the code."""

from __future__ import annotations

from typing import Any, Protocol


class ModelRunner(Protocol):
    def generate(self, system: str, data_block: str, schema: dict[str, Any], timeout_s: float) -> str:
        """Return the model's raw text for a fixed system text and a fenced data block."""
        ...
