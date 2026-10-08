import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from website_summarizer.ingest import (
    IngestError,
    apply_char_budget,
    extract_article,
    fetch_page,
    looks_like_login_wall,
    validate_public_url,
)

FIXTURES = Path(__file__).parent / "fixtures"
TEST_URL = "https://docs.pytest.org/en/stable/index.html"


def test_extracts_article_not_chrome() -> None:
    html = (FIXTURES / "harbor.html").read_text(encoding="utf-8")
    page = extract_article(html, "https://harbor.example/lanterns", max_chars=24_000)
    assert "Harbor lanterns return to Pier 4" in (page.title or "") + page.text
    assert "copper lanterns" in page.text
    assert "cookie settings" not in page.text.lower()
    assert page.truncated is False


def test_login_wall_is_rejected() -> None:
    html = (FIXTURES / "login.html").read_text(encoding="utf-8")
    assert looks_like_login_wall(html, "Sign in")
    with pytest.raises(IngestError) as exc:
        extract_article(html, "https://example.com/login", max_chars=24_000)
    assert exc.value.kind == "login_wall"


def test_char_budget_truncates() -> None:
    text, truncated = apply_char_budget("alpha " * 50, max_chars=40)
    assert truncated is True
    assert "Truncated" in text
    assert len(text) < 80


def test_rejects_non_http_urls() -> None:
    with pytest.raises(IngestError):
        validate_public_url("file:///etc/passwd")
    with pytest.raises(IngestError):
        validate_public_url("https://user:pass@example.com/")
    assert validate_public_url(" " + TEST_URL + " ") == TEST_URL


def test_fetch_page_uses_configured_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[str] = []
    html = (FIXTURES / "harbor.html").read_text(encoding="utf-8")

    class Page:
        url = TEST_URL

        async def goto(self, url: str, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(status=200)

        async def wait_for_load_state(self, state: str, timeout: int) -> None:
            return None

        async def content(self) -> str:
            return html

    class Browser:
        async def new_page(self) -> Page:
            return Page()

        async def close(self) -> None:
            return None

    class Launcher:
        def __init__(self, name: str) -> None:
            self.name = name

        async def launch(self, *, headless: bool) -> Browser:
            launched.append(self.name)
            return Browser()

    class PlaywrightContext:
        async def __aenter__(self) -> SimpleNamespace:
            return SimpleNamespace(
                chromium=Launcher("chromium"),
                firefox=Launcher("firefox"),
                webkit=Launcher("webkit"),
            )

        async def __aexit__(self, *args: object) -> None:
            return None

    async_api = SimpleNamespace(
        Error=Exception,
        TimeoutError=TimeoutError,
        async_playwright=PlaywrightContext,
    )
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)

    page = asyncio.run(
        fetch_page(TEST_URL, timeout_ms=1000, max_chars=24_000, browser_type="webkit")
    )

    assert launched == ["webkit"]
    assert page.final_url == TEST_URL
