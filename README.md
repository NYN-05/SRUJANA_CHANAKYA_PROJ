# VeriDoc

**From chat to verified document, while you're still chatting.**

VeriDoc is a local-first tool that turns a WhatsApp deal conversation into a tamper-evident record. It reads a chat on the user's own laptop, finds the key terms of the deal, flags what is ambiguous, missing or contradictory, helps both sides confirm a plain-language recap, and keeps a record that anyone can check offline.

It is a drafting and record-keeping aid. It is **not legal advice**, and it checks that a record was not changed after it was saved. It cannot prove that the original chat export was genuine.

> **Project status: early development.** The design is documented in full, and the first three build phases are written. **Nothing has been run or verified yet**, and there is no runnable application. See [Project status](#project-status) before relying on anything below.

## Table of contents

- [Problem](#problem)
- [How it works](#how-it-works)
- [Key features](#key-features)
- [Project status](#project-status)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [Setup](#setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Limits](#limits)

## Problem

The project addresses **LS-06, From Handshake to Contract (informal agreements)** in the Legal Services track.

Small suppliers, freelancers and tutors close deals on WhatsApp. The price is in one message, a changed deadline is in a voice note, and the payment term was never said. When a dispute starts, nobody can show what was actually agreed.

Example: Raju (a cloth wholesaler) and Meena (a tailor) agree on 200 shirts at ₹480 each. Raju says "advance half now" and Meena sends ₹48,000. Meena says "delivery next week". Nobody says when the balance is due or what happens if delivery is late.

## How it works

The core flow is **Handshake, Recap, Receipt**.

1. **Handshake.** The two sides chat as usual. VeriDoc reads the chat, extracts terms (price, quantity, delivery date, advance, balance, late penalty and so on), links each term to the exact message it came from, and flags gaps. It suggests one friendly next message that closes the biggest gap.
2. **Recap.** After the user confirms the terms, VeriDoc builds a short recap with a 4-character echo code. The other side confirms by replying `CONFIRM <code>` in WhatsApp, installing nothing.
3. **Receipt.** Every message and each agreement version is hashed into a Merkle tree and a version chain. The result is a receipt bundle that a static offline page, or a Python verifier, can check.

## Key features

The list below is the design. The **Status** column says what exists in this repository today.

| Feature | Status |
|---|---|
| Integrity core: SHA-256 with domain separation, RFC 8785 canonical JSON, salted Merkle tree, version chain, echo code, timestamps, receipt hash (Python and JavaScript) | Written (Phase 1), not yet run |
| WhatsApp import: Android and iPhone `.txt` exports, pasted text, `.zip` with media, preview, party selection, three sample chats | Written (Phase 2), not yet run |
| Playbooks (YAML) for supply orders and freelance work, deterministic rules parsers (amounts, quantities, dates, percentages, payments, penalties) and rules-only term extraction | Written (Phase 3), not yet run |
| Flags, Evidence Strength score, suggested next message | Planned (Phase 4) |
| Encrypted local vault, human confirmation, agreement versions | Planned (Phase 5) |
| Recap and echo-code confirmation | Planned (Phase 6) |
| Receipt bundle, Python verifier, single-file offline `verify.html`, tamper tests | Planned (Phase 7) |
| Local open-source LLM as a refiner only, with grounding and prompt-injection defence | Planned (Phase 8) |
| Local API, web UI, end-to-end demo flow | Planned (Phase 9) |
| Evaluation, hardening, packaging | Planned (Phase 10) |
| Voice-note transcription, Blind Handshake, dispute-pack PDF, Kannada, fine-tuning | Deferred (Phase 11) |

Design principles:

- **Rules first, AI second.** Parsing, flags, score, recap and hashing are deterministic. A model can only propose terms, and the product works with it switched off.
- **A person confirms every term.** Only confirmed terms reach a version, a recap or a hash.
- **Local-first.** Chats stay on the user's device. Nothing is uploaded.
- **Tamper-evident, never "proof of authenticity".** The wording rules are in [Honest Limits](DOCS/PRODUCT.md#honest-limits).

## Project status

| Item | State |
|---|---|
| Documentation and phase plan | Written: [PHASES.md](PHASES.md) and [DOCS/](DOCS/) |
| Test suite for phases 0 to 11 | Written under `tests/`; only the phases below have code behind them |
| Phase 0 (project tooling, settings, API skeleton) | **Not built.** There is no `pyproject.toml`, `uv.lock` or `apps/api` yet |
| Phases 1 to 3 (contracts, integrity, ingest, playbooks, rules engine) | Code written; **not executed or verified** |
| Phases 4 to 10 | Not started |
| Phase 11 | Deferred until the MVP gate passes |

Per-phase detail, including every decision that resolves a conflict between documents, is in [PHASES.md](PHASES.md). A running change history is in [CHANGES.md](CHANGES.md).

## Architecture

```
WhatsApp export / pasted text / sample
        |
        v
packages/ingest        parse, preview, choose parties, build a commit draft
        |
        v
packages/intelligence  playbooks + rules engine (+ optional local model, later)
        |   proposes terms, flags, score, suggestion   (never writes evidence)
        v
   human confirms each term
        |
        v
packages/vault         encrypted local storage, versions        (planned)
        |
        v
packages/integrity     hashing, Merkle tree, version chain, echo code, receipt
        |
        v
receipt bundle  ->  Python verifier / offline verify.html       (planned)
```

Dependency rules, enforced by a test (`tests/phase_00/test_dependency_guards.py`):

- Packages import across package lines only through `packages.contracts`. The vault may also call `packages.integrity`.
- `packages/intelligence` never imports the vault or the hashing code, so the AI layer cannot touch evidence.
- Network libraries are allowed only in the anchoring and share modules (both deferred).

The full architecture, decisions (ADRs), data model and specifications are in [DOCS/TECHNICAL.md](DOCS/TECHNICAL.md).

## Technology stack

| Area | Choice |
|---|---|
| Language | Python 3.11 or later; JavaScript (no framework) for the offline verifier |
| Backend (planned) | FastAPI, Pydantic v2, pydantic-settings |
| Storage (planned) | SQLite in WAL mode, SQLAlchemy 2, Alembic; AES-GCM with Argon2id key derivation |
| Canonical JSON | `rfc8785` (Python); an inline implementation in `apps/verify/integrity.mjs` |
| Playbooks | YAML via `pyyaml` |
| Local model (planned) | `llama.cpp` through `llama-cpp-python` with an existing open instruction model; no fine-tuning |
| Tooling (planned) | `uv`, `pytest`, `ruff`, `mypy`, `pre-commit`; Node.js 20 or later for the JavaScript tests |

Libraries marked planned are specified in [PHASES.md](PHASES.md) (Phase 0, task 1) but are not installed by anything in this repository yet.

## Repository layout

```
DOCS/                  Product (PRD, UX, limits), Technical (architecture, specs), Team, Demo
PHASES.md              Implementation plan for phases 0 to 11, with acceptance criteria
CHANGES.md             Change log, appended after each phase
packages/
  contracts/           Shared Pydantic models and enums
  integrity/           Hashing, Merkle tree, version chain, echo code, receipt hash
  ingest/              WhatsApp parser, preview, commit draft, zip reader, samples
  intelligence/        Playbook loader, normaliser, rules parsers, term extraction
apps/verify/           integrity.mjs: the integrity primitives in JavaScript
playbooks/             supply_order.yaml and freelance.yaml
eval/                  Sample chats, gold labels and the metrics helper
scripts/               make_test_vectors.py
test-vectors/          Cross-language integrity vectors (generated; see Testing)
tests/                 Phase-by-phase test suite and the gate runner
```

## Setup

There is no installable application yet, because Phase 0 (project tooling) has not been built. These steps prepare a development environment for the code that exists.

Prerequisites: Git, Python 3.11 or later, and Node.js 20 or later (only for the JavaScript tests).

```bash
git clone https://github.com/NYN-05/SRUJANA_CHANAKYA_PROJ.git
cd SRUJANA_CHANAKYA_PROJ

python -m venv .venv
# macOS / Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install pytest pydantic rfc8785 pyyaml
```

These are the runtime libraries the Phase 1 to 3 code imports, plus `pytest`. Phase 0 will replace this step with a single `uv sync` from a `pyproject.toml`.

## Usage

There is no command-line tool, server or web interface yet. The code is used as a library.

Parse a WhatsApp export and prepare a commit draft:

```python
from packages.contracts import MessageOrigin
from packages.ingest.commit import prepare_commit
from packages.ingest.samples import load_sample
from packages.ingest.whatsapp import parse_export

result = parse_export(load_sample("ambiguous"))   # bytes = a file, str = pasted text
draft = prepare_commit(
    result, me="Raju", counterparty="Meena",
    playbook_key="supply_order", origin=MessageOrigin.EXPORT,
)
```

Extract terms with the rules engine:

```python
from packages.intelligence.extract import extract_terms
from packages.intelligence.playbooks import load_playbook

playbook = load_playbook("playbooks/supply_order.yaml")
terms = extract_terms(
    draft.messages, playbook,
    me_id=draft.me_id, counterparty_id=draft.counterparty_id,
    date_order=result.date_order, eligible_ids=draft.eligible_message_ids,
)
for t in terms:
    print(t.key, t.state.value, t.value)
```

Run scripts from the project root so that `packages` can be imported. Generate the integrity test vectors:

```bash
python scripts/make_test_vectors.py          # writes test-vectors/integrity/*.json
python scripts/make_test_vectors.py --check  # fails if the files differ from the code
```

## Configuration

Planned settings are specified in [DOCS/TECHNICAL.md](DOCS/TECHNICAL.md) (Architecture, section 12) and use the `VERIDOC_` prefix, for example `VERIDOC_HOME`, `VERIDOC_PORT`, `VERIDOC_SAFE_MODE`, `VERIDOC_MODEL_MODE`, `VERIDOC_MAX_IMPORT_MB` and `VERIDOC_FEATURE_FLAGS`. The settings module (`apps/api/settings.py`) belongs to Phase 0 and does not exist yet, so nothing reads them today.

Behaviour that is configurable today lives in data, not code:

- `playbooks/*.yaml`: required terms, weights, cue words, ambiguity rules, legal hints and handshake questions. A new valid playbook in this folder needs no code change. The format is in [DOCS/TECHNICAL.md](DOCS/TECHNICAL.md) (Playbooks).
- `parse_export(..., utc_offset="+05:30")`: exports carry no offset, so the local one is a parameter.

Never commit secrets. `.env` files, keys, model weights and local databases are ignored by `.gitignore`.

## Testing

The tests are organised by phase under `tests/phase_NN/`, with shared fixtures in `tests/conftest.py`. A phase passes only when its cumulative gate does:

```bash
python tests/run_gate.py N      # runs phases 0..N in gate mode (skipped tests fail)
```

Rules of the gate are in [PHASES.md](PHASES.md) section 5. Two things to know right now:

- **Phase 0 tests fail by design** until Phase 0 is built, and every gate includes them. To work on a later phase in the meantime, run its folder directly, for example `python -m pytest tests/phase_01`.
- **The integrity vector files are not committed yet.** Run `python scripts/make_test_vectors.py` once before the Phase 1 vector tests, and run the JavaScript parity test with `node --test "tests/phase_01/js/*.test.mjs"` (the glob must be quoted).

Tests for phases 4 to 10 import code that does not exist yet and will fail until those phases are built. Phase 11 tests are specifications for deferred features (marker `deferred`) and are never part of a gate.

## Documentation

| Document | Contents |
|---|---|
| [PHASES.md](PHASES.md) | The build plan, decisions that resolve conflicts, interface reference, and acceptance criteria per phase |
| [DOCS/PRODUCT.md](DOCS/PRODUCT.md) | PRD, UX flows, user research, roadmap, honest limits, glossary, open questions |
| [DOCS/TECHNICAL.md](DOCS/TECHNICAL.md) | Architecture, ADRs, data model, integrity specification, AI specification, playbooks, evaluation, threat model |
| [DOCS/TEAM.md](DOCS/TEAM.md) | Onboarding, team guide, developer setup, Git workflow, release checklist |
| [DOCS/DEMO.md](DOCS/DEMO.md) | Demo script, runbook and judge Q&A |
| [CHANGES.md](CHANGES.md) | What changed in each phase |

## Contributing

The full rules are in [DOCS/TEAM.md](DOCS/TEAM.md) (Team Guide and Git Workflow). In short:

- Follow the phases in order. Do not start a later phase's work early, and do not claim an unbuilt feature in code, UI or docs.
- Branches: `feat/<area>-<name>`, `fix/<name>`, `docs/<name>`, `chore/<name>`.
- Commits: Conventional Commits, small and logical (for example `feat(ingest): parse iPhone export headers`).
- Pull requests: small, linked to requirement IDs, with tests. Contract changes (`packages/contracts`) need approval from both engineering owners.
- Do not delete, weaken or skip a test to make a gate pass. If a test is wrong, fix it in its own pull request with the reason.
- Never put message text, names, amounts or file names in logs. Never commit secrets.
- Any change to hashing, Merkle, chain, echo code or verify logic must update the specification and the test vectors in the same change.

The Git Workflow document describes `main` and `dev` branches. This repository currently has only `main`; follow the Git Workflow document once the team creates `dev`.

## Limits

- VeriDoc checks that a record was not changed after it was saved. It cannot prove that the original chat export was genuine.
- The device clock is trusted unless the receipt is anchored (anchoring is deferred and off by default).
- The 4-character echo code is a binding check between a reply and a recap, not authentication of who typed the reply.
- Hindi text, legal hints and legal wording are drafts that need native-speaker and lawyer review. All accuracy and speed figures in the documents are targets, not measurements.

The full list is in [Honest Limits](DOCS/PRODUCT.md#honest-limits).
