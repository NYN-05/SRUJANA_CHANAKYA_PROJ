"""Phase 10: browser checks with Playwright (NFR-OFF-002, NFR-ACX-002, NFR-ACX-003).

Needs: uv sync --extra browser && uv run playwright install chromium.
Screens expose data-testid attributes listed in PHASES.md Phase 9, task 5.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
SCREENS = ["/", "/import", "/settings"]


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    home = tmp_path_factory.mktemp("home")
    env = dict(os.environ, VERIDOC_HOME=str(home), VERIDOC_MODEL_MODE="fake", VERIDOC_PORT=str(port), VERIDOC_DEMO_MODE="1")
    proc = subprocess.Popen([sys.executable, str(ROOT / "packaging" / "launch.py"), "--no-browser"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


class Browsed:
    def __init__(self, page, outside_requests, console_errors):
        self.page, self.outside_requests, self.console_errors = page, outside_requests, console_errors


@pytest.fixture
def page(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        outside = []

        def guard(route):
            if route.request.url.startswith(base_url):
                route.continue_()
            else:
                outside.append(route.request.url)
                route.abort()

        ctx.route("**/*", guard)
        pg = ctx.new_page()
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        yield Browsed(pg, outside, errors)
        browser.close()


@pytest.mark.parametrize("path", SCREENS)
def test_screen_loads_with_network_blocked(page, base_url, path):
    page.page.goto(base_url + path)
    page.page.wait_for_load_state("networkidle")
    assert page.outside_requests == [], page.outside_requests
    assert page.console_errors == []
    assert "Offline mode" in page.page.content()


def test_keyboard_only_import_to_workspace(page, base_url):
    page = page.page
    page.goto(base_url + "/import")
    for _ in range(60):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.dataset.testid") == "sample-ambiguous":
            break
    else:
        pytest.fail("sample button not reachable by keyboard")
    page.keyboard.press("Enter")
    page.get_by_test_id("which-one-is-you").focus()
    page.keyboard.press("ArrowDown")
    page.get_by_test_id("analyse").focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("[data-testid=score-value]")
    assert page.get_by_test_id("term-row-delivery_date").inner_text().count("! Ambiguous") == 1


def test_zoom_200_keeps_primary_action_visible(page, base_url):
    page = page.page
    page.goto(base_url + "/import")
    page.evaluate("document.body.style.zoom = '200%'")
    assert page.get_by_test_id("analyse").is_visible()


def test_body_text_at_least_16px(page, base_url):
    page = page.page
    page.goto(base_url + "/")
    size = page.evaluate("parseFloat(getComputedStyle(document.body).fontSize)")
    assert size >= 16
