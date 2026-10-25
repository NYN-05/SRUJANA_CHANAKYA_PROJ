"""Run the cumulative gate for one phase.

Usage:  uv run python tests/run_gate.py N [extra pytest args]

Runs tests/phase_00 ... tests/phase_NN in gate mode. Markers that belong to a
later or special gate (perf, model, browser, deferred) are deselected, which is
not the same as skipping: the gate itself must report 0 skipped.
See PHASES.md section 5.3.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
LAST_PHASE = 10  # Phase 11 is deferred and never part of a gate run


def main(argv: list[str]) -> int:
    if not argv or not argv[0].isdigit():
        print(__doc__)
        return 2
    phase = int(argv[0])
    if not 0 <= phase <= LAST_PHASE:
        print(f"phase must be 0..{LAST_PHASE}; Phase 11 items run with: pytest tests/phase_11 -m deferred --gate")
        return 2
    paths = [str(TESTS / f"phase_{n:02d}") for n in range(phase + 1)]
    missing = [p for p in paths if not Path(p).is_dir()]
    if missing:
        print("missing test folders:", *missing, sep="\n  ")
        return 2
    marker = "not perf and not model and not browser and not deferred"
    args = [*paths, "--gate", "-m", marker, "-p", "no:cacheprovider", *argv[1:]]
    print(f"VeriDoc gate for Phase {phase}: phases 0..{phase}")
    return int(pytest.main(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
