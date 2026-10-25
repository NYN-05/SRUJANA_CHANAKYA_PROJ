"""A recorded-output runner for tests and for the default fake mode (``VERIDOC_MODEL_MODE=fake``)."""

from __future__ import annotations

import time
from typing import Any


class FakeModelRunner:
    """Returns ``response`` after ``delay_s`` seconds, or raises ``error``. ``calls`` records each
    ``(system, data_block, schema)`` it was given."""

    def __init__(self, response: str, delay_s: float = 0.0, error: BaseException | None = None) -> None:
        self.response, self.delay_s, self.error = response, delay_s, error
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def generate(self, system: str, data_block: str, schema: dict[str, Any], timeout_s: float) -> str:
        self.calls.append((system, data_block, schema))
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return self.response
