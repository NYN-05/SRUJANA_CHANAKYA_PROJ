"""Evidence Strength score (FR-SCO-001 to 003; I-06). Exact Decimal arithmetic, rounded half up."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from packages.contracts import ScoreResult, ScoreRow, TermState

from .playbooks import Playbook

PRESENT, CLEAR, ACK = Decimal("0.4"), Decimal("0.3"), Decimal("0.3")


@dataclass(frozen=True)
class ScoreInput:
    key: str
    confirmed: bool
    state: TermState
    acknowledged_by_both: bool


@dataclass(frozen=True)
class ScoreDelta:
    before: int
    after: int

    @property
    def delta(self) -> int:
        return self.after - self.before


def factor(item: ScoreInput | None) -> Decimal:
    """0.4 present + 0.3 clear + 0.3 acknowledged (acknowledgement counts only when present)."""
    if item is None:
        return Decimal(0)
    present = item.confirmed and item.state != TermState.MISSING
    clear = present and item.state == TermState.STATED
    return PRESENT * present + CLEAR * clear + ACK * (present and item.acknowledged_by_both)


def compute_score(inputs: Sequence[ScoreInput], playbook: Playbook) -> ScoreResult:
    """Score over the required terms of the playbook; unknown and non-required keys are ignored."""
    by_key = {i.key: i for i in inputs}
    rows = []
    for term in (t for t in playbook.terms if t.required):
        item = by_key.get(term.key)
        present = item is not None and item.confirmed and item.state != TermState.MISSING
        clear = present and item.state == TermState.STATED  # type: ignore[union-attr]
        acknowledged = present and item.acknowledged_by_both  # type: ignore[union-attr]
        rows.append(
            ScoreRow(key=term.key, weight=Decimal(term.weight), present=present, clear=clear, acknowledged=acknowledged,
                     points=Decimal(term.weight) * factor(item))
        )
    total = sum((r.points for r in rows), Decimal(0))
    return ScoreResult(
        score=int(total.quantize(Decimal(1), ROUND_HALF_UP)),
        rows=rows,
        present_count=sum(r.present for r in rows),
        clear_count=sum(r.clear for r in rows),
        acknowledged_count=sum(r.acknowledged for r in rows),
        total=len(rows),
    )
