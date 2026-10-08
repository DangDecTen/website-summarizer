from __future__ import annotations

import sys
import asyncio
import time
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from website_summarizer.config import load_settings
from website_summarizer.ingest import IngestError, fetch_page, validate_public_url
from website_summarizer.llm import LLMError
from website_summarizer.models import PageReport
from website_summarizer.tasks import LANGUAGE_LABELS, run_report

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

app = FastAPI(title="website-summarizer", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


def _form_context(
    *,
    url: str = "",
    language: str = "en",
    model: str | None = None,
    error: str | None = None,
    report: PageReport | None = None,
    markdown: str | None = None,
    elapsed: float | None = None,
) -> dict:
    settings = load_settings()
    return {
        "url": url,
        "language": language,
        "languages": LANGUAGE_LABELS,
        "model": model or settings.default_model,
        "models": settings.model_choices(),
        "error": error,
        "report": report,
        "markdown": markdown,
        "elapsed": elapsed,
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_form_context(),
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    url: str = Form(...),
    language: str = Form("en"),
    model: str = Form(...),
) -> HTMLResponse:
    settings = load_settings()
    if language not in LANGUAGE_LABELS:
        language = "en"
    allowed = settings.model_choices()
    if model not in allowed:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_form_context(
                url=url,
                language=language,
                model=settings.default_model,
                error="Unknown model. Pick one from the list.",
            ),
            status_code=400,
        )

    started = time.perf_counter()
    try:
        validate_public_url(url)
        page = await fetch_page(
            url,
            timeout_ms=settings.fetch_timeout_ms,
            max_chars=settings.max_extract_chars,
            browser_type=settings.playwright_browser,
        )
        report = run_report(
            page,
            language_code=language,
            model=model,
            settings=settings,
            elapsed_seconds=time.perf_counter() - started,
        )
    except IngestError as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_form_context(
                url=url,
                language=language,
                model=model,
                error=str(exc),
                elapsed=time.perf_counter() - started,
            ),
            status_code=400,
        )
    except LLMError as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_form_context(
                url=url,
                language=language,
                model=model,
                error=str(exc),
                elapsed=time.perf_counter() - started,
            ),
            status_code=502,
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_form_context(
            url=url,
            language=language,
            model=model,
            report=report,
            markdown=report.to_markdown(),
            elapsed=report.elapsed_seconds,
        ),
    )


@app.post("/download")
async def download(markdown: str = Form(...), title: str = Form("report")) -> PlainTextResponse:
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "" for ch in title).strip() or "report"
    filename = f"{safe[:60]}.md"
    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    loop = asyncio.get_running_loop()

    return {
        "status": "ok",
        "python": sys.version,
        "loop": type(loop).__name__,
        "loop_module": type(loop).__module__,
    }


@app.get("/analyze")
async def analyze_get() -> RedirectResponse:
    return RedirectResponse("/", status_code=303)


def main() -> None:
    uvicorn.run(
        "website_summarizer.web:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )

