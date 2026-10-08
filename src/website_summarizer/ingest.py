from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from readability import Document
from trafilatura import extract, extract_metadata

LOGIN_HINTS = (
    "sign in",
    "log in",
    "login",
    "create an account",
    "forgot password",
    "đăng nhập",
)


class IngestError(Exception):
    def __init__(self, message: str, kind: str = "error") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class ExtractedPage:
    url: str
    final_url: str
    html: str
    text: str
    title: str | None
    author: str | None
    published: str | None
    truncated: bool
    char_count: int


def validate_public_url(url: str) -> str:
    candidate = url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IngestError(
            "Enter a public http(s) URL. This tool only fetches pages you paste — "
            "it does not crawl, log in, or bypass paywalls.",
            kind="invalid_url",
        )
    if parsed.username or parsed.password:
        raise IngestError(
            "URLs with embedded credentials are not allowed.",
            kind="invalid_url",
        )
    return candidate


def apply_char_budget(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    clipped = text[:max_chars]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    note = "\n\n[Truncated for the model context budget.]"
    return clipped + note, True


def looks_like_login_wall(html: str, text: str | None) -> bool:
    if text and len(text.strip()) >= 400:
        return False
    lower = html.lower()
    has_password = 'type="password"' in lower or "type='password'" in lower
    hinted = any(hint in lower for hint in LOGIN_HINTS)
    return has_password and hinted


def extract_article(html: str, url: str, max_chars: int) -> ExtractedPage:
    if not html or not html.strip():
        raise IngestError("The page returned an empty body.", kind="empty")

    text = extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    metadata = extract_metadata(html, default_url=url)
    title = metadata.title if metadata else None
    author = metadata.author if metadata else None
    published = metadata.date if metadata else None

    if not text:
        document = Document(html)
        title = title or (document.short_title() or None)
        summary_html = document.summary(html_partial=True)
        text = _strip_tags(summary_html)

    if looks_like_login_wall(html, text):
        raise IngestError(
            "This looks like a login or paywall page. v1 only supports public pages "
            "and will not submit credentials or solve CAPTCHAs.",
            kind="login_wall",
        )

    if not text or len(text.strip()) < 40:
        raise IngestError(
            "Could not extract a main article from this page (too little body text).",
            kind="empty",
        )

    budgeted, truncated = apply_char_budget(text.strip(), max_chars)
    return ExtractedPage(
        url=url,
        final_url=url,
        html=html,
        text=budgeted,
        title=title,
        author=author,
        published=published,
        truncated=truncated,
        char_count=len(budgeted),
    )


async def fetch_page(
    url: str,
    timeout_ms: int,
    max_chars: int,
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
) -> ExtractedPage:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeout
    from playwright.async_api import async_playwright

    validated = validate_public_url(url)
    try:
        async with async_playwright() as playwright:
            browser = await getattr(playwright, browser_type).launch(headless=True)
            try:
                page = await browser.new_page()
                response = await page.goto(
                    validated,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(5_000, timeout_ms))
                except PlaywrightTimeout:
                    pass
                status = response.status if response is not None else 0
                final_url = page.url
                html = await page.content()
            finally:
                await browser.close()
    except PlaywrightTimeout as exc:
        raise IngestError(
            f"Timed out after {timeout_ms}ms waiting for the page.",
            kind="timeout",
        ) from exc
    except PlaywrightError as exc:
        raise IngestError(f"Browser failed to load the page: {exc}", kind="fetch") from exc

    if status in {401, 403}:
        raise IngestError(
            f"The site returned HTTP {status}. Login-walled or blocked pages are out of scope.",
            kind="http",
        )
    if status and status >= 400:
        raise IngestError(f"The site returned HTTP {status}.", kind="http")

    extracted = extract_article(html, validated, max_chars)
    return ExtractedPage(
        url=validated,
        final_url=final_url,
        html=extracted.html,
        text=extracted.text,
        title=extracted.title,
        author=extracted.author,
        published=extracted.published,
        truncated=extracted.truncated,
        char_count=extracted.char_count,
    )


def _strip_tags(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
