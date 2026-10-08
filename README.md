# website-summarizer

Paste a **public URL**. The app opens it in a headless Playwright browser, extracts the main article (not the nav/ads chrome), and asks an LLM for a structured report: **translation**, **content analysis**, and a **summary** you can copy or download as Markdown.

This is a **single-URL analyst**, not a crawler. One page per run.

## Fetch policy (read this first)

- Only the URL **you type** is fetched.
- Public `http`/`https` pages only. No embedded credentials, no `file://`.
- Login walls, paywalls, HTTP 401/403, and CAPTCHAs fail with a clear error.
- v1 will **not** fill login forms, solve CAPTCHAs, or walk additional links.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) recommended (`pip` + `venv` also works)
- Chromium, Firefox, or WebKit for Playwright (Firefox by default)
- For local models: [Ollama](https://ollama.com/) running on `127.0.0.1:11434`

## Setup

```bash
cd C:\dev\work-repos\website-summarizer
uv sync
uv run playwright install firefox
copy .env.example .env
```

Fill the keys you actually use in `.env`. Unused providers can stay empty.
Set `PLAYWRIGHT_BROWSER` to `chromium`, `firefox`, or `webkit` to choose an engine. The default is `firefox`.
Install that engine with `uv run playwright install firefox` or `uv run playwright install webkit`.

```bash
# optional local model
ollama pull llama3.2
```

## Run

```bash
uv run website-summarizer
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Paste a news or docs URL, pick English or Vietnamese, pick a cloud model or `ollama/llama3.2`.

Equivalent:
    
```bash
uv run python -m website_summarizer
```

## Tests

Tests use a fixture HTML page and a mocked LLM. They do **not** hit the live web.

```bash
uv run pytest
```

## Architecture

```
UI (Jinja) → FastAPI → Playwright → trafilatura → LiteLLM → report Markdown
                                         ↘ readability-lxml fallback
                              LiteLLM  → OpenAI / Anthropic / Gemini
                                       → Ollama
```

| Module | Role |
| --- | --- |
| `src/website_summarizer/ingest.py` | URL checks, Playwright fetch, extract, char budget |
| `src/website_summarizer/llm.py` | One `completion()` path via LiteLLM |
| `src/website_summarizer/tasks.py` | Translate / analyze / summarize prompt |
| `src/website_summarizer/web.py` | Local UI + Markdown download |

Long pages are clipped to `MAX_EXTRACT_CHARS` (default 24 000) before they reach the model. The UI shows model name and elapsed time.

## GitHub later

This folder is a git repo. There is no remote until you want one:

```bash
gh repo create website-summarizer --private --source . --remote origin
git push -u origin HEAD
```

Do not commit `.env`.

## Out of scope for v1

Login/paywalled sites, multi-page crawls, scheduled jobs, hosted deploy, fine-tuning, and agents that click around the web.
