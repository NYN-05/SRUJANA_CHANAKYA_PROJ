"""Phase 0: repository layout (PHASES.md Phase 0, tasks 1, 2, 6, 7)."""

from __future__ import annotations

import re
import subprocess

import pytest

REQUIRED_FILES = [
    "pyproject.toml",
    "uv.lock",
    ".env.example",
    ".gitignore",
    "models/manifest.json",
    "packages/__init__.py",
    "packages/contracts/__init__.py",
    "packages/ingest/__init__.py",
    "packages/intelligence/__init__.py",
    "packages/integrity/__init__.py",
    "packages/vault/__init__.py",
    "apps/__init__.py",
    "apps/api/__init__.py",
    "apps/api/main.py",
    "apps/api/settings.py",
    "apps/api/routers/__init__.py",
]

REQUIRED_DIRS = [
    "apps/web",
    "apps/verify",
    "playbooks/templates/en",
    "playbooks/templates/hi",
    "eval/chats",
    "eval/labels",
    "eval/runner",
    "scripts",
    "test-vectors/integrity",
]

ENV_NAMES = [
    "VERIDOC_HOME",
    "VERIDOC_PORT",
    "VERIDOC_TIER",
    "VERIDOC_SAFE_MODE",
    "VERIDOC_MODEL_MODE",
    "VERIDOC_MODEL_DIR",
    "VERIDOC_MANIFEST_PATH",
    "VERIDOC_MAX_IMPORT_MB",
    "VERIDOC_LOG_LEVEL",
    "VERIDOC_DEMO_MODE",
    "VERIDOC_FEATURE_FLAGS",
    "VERIDOC_ANCHOR_ENABLED",
]


@pytest.mark.parametrize("rel", REQUIRED_FILES)
def test_required_file_exists(project_root, rel):
    assert (project_root / rel).is_file(), f"missing {rel}"


@pytest.mark.parametrize("rel", REQUIRED_DIRS)
def test_required_dir_exists(project_root, rel):
    assert (project_root / rel).is_dir(), f"missing folder {rel}"


def test_env_example_lists_names_without_values(project_root):
    lines = [
        ln.strip()
        for ln in (project_root / ".env.example").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    names = {ln.split("=", 1)[0] for ln in lines}
    for name in ENV_NAMES:
        assert name in names, f".env.example is missing {name}"
    for ln in lines:
        assert re.fullmatch(r"[A-Z0-9_]+=?", ln), f".env.example must hold names only, found: {ln!r}"


@pytest.mark.parametrize(
    "pattern", [".env", "*.gguf", "*.bin", "*.safetensors", "eval/reports/"]
)
def test_gitignore_blocks_sensitive_and_generated_files(project_root, pattern):
    text = (project_root / ".gitignore").read_text(encoding="utf-8")
    assert pattern in text.split(), f".gitignore must contain {pattern}"


def test_no_model_weights_in_repository(project_root):
    weights = [
        p
        for ext in ("*.gguf", "*.safetensors", "*.ggml", "*.pt")
        for p in project_root.rglob(ext)
        if ".venv" not in p.parts
    ]
    assert weights == [], f"model weights must never be committed: {weights}"


def test_no_env_file_tracked_by_git(project_root):
    if not (project_root / ".git").exists():
        pytest.fail("Phase 0 requires a git repository (PHASES.md Phase 0)")
    out = subprocess.run(
        ["git", "ls-files", ".env"], cwd=project_root, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "", ".env must never be committed"
