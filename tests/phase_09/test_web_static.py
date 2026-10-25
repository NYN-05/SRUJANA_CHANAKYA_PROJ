"""Phase 9: web UI files are offline, token-based and use the required copy (NFR-OFF-002, NFR-ACX-001, UX global rules)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"
TOKENS = WEB / "assets" / "design-tokens.css"
MVP_SCREENS = ["s1-deals", "s2-import", "s3-workspace", "s4-term", "s6-recap", "s7-versions", "s8-receipt", "s11-settings"]
DEFERRED_SCREENS = ["s5-handshake", "s10-dispute-pack"]


def web_files(*exts):
    return [p for p in WEB.rglob("*") if p.is_file() and p.suffix in exts]


def test_web_folder_and_tokens_exist():
    assert WEB.is_dir() and TOKENS.is_file()


@pytest.mark.parametrize("screen", MVP_SCREENS)
def test_mvp_screen_exists(screen):
    folder = WEB / "screens" / screen
    assert folder.is_dir() and any(folder.iterdir())


@pytest.mark.parametrize("screen", DEFERRED_SCREENS)
def test_deferred_screens_say_so(screen):
    text = "".join(p.read_text(encoding="utf-8") for p in (WEB / "screens" / screen).rglob("*") if p.is_file())
    assert "Not in this build" in text, "PHASES.md R-02: deferred screens must not pretend to work"


def test_no_external_urls():
    pattern = re.compile(r"""(?:src|href|url)\s*[=(]\s*["']?(https?:)?//""", re.I)
    for p in web_files(".html", ".css", ".js", ".mjs"):
        text = p.read_text(encoding="utf-8")
        assert not pattern.search(text), f"{p.relative_to(ROOT)} loads something from outside the device"
        assert "cdn" not in text.lower() or p == TOKENS


def test_colours_only_in_tokens_file():
    colour = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(")
    for p in web_files(".css", ".html"):
        if p == TOKENS:
            continue
        assert not colour.search(p.read_text(encoding="utf-8")), f"raw colour in {p.relative_to(ROOT)}"


def test_fonts_bundled():
    fonts = list((WEB / "assets" / "fonts").glob("*.woff2"))
    names = " ".join(f.name.lower() for f in fonts)
    assert "devanagari" in names, "Noto Sans Devanagari must be bundled"


def test_status_labels_are_symbol_and_word():
    text = "".join(p.read_text(encoding="utf-8") for p in web_files(".js", ".mjs", ".html", ".json"))
    for label in ("✓ Clear", "! Ambiguous", "○ Missing", "⚠ Conflict"):
        assert label in text


@pytest.mark.parametrize(
    "copy",
    [
        "This chat stays on this device. Nothing is uploaded.",
        "Drafting aid, not legal advice. Please read each line before confirming.",
        "This checks that the record was not changed after it was saved. It cannot prove that the original chat export was genuine.",
        "Every extracted term needs a person to confirm it. Nothing is added to the record automatically.",
        "Safe mode: rules only. The AI helper is off.",
    ],
)
def test_required_copy_present(copy):
    text = "".join(p.read_text(encoding="utf-8") for p in web_files(".js", ".mjs", ".html", ".json"))
    assert copy in text


@pytest.mark.parametrize("banned", ["proof of authenticity", "proves the chat is real", "fake detection", "legally binding", "guaranteed"])
def test_banned_wording_absent(banned):
    text = "".join(p.read_text(encoding="utf-8") for p in web_files(".js", ".mjs", ".html", ".json")).lower()
    assert banned not in text


def test_no_emoji_in_ui_copy():
    emoji = re.compile("[\U0001F300-\U0001FAFF]")
    for p in web_files(".html", ".json"):
        assert not emoji.search(p.read_text(encoding="utf-8")), p
