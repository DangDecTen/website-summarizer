from __future__ import annotations

import json
import os
import re
from typing import Any

import litellm

from website_summarizer.config import Settings
from website_summarizer.models import PageReport, ContentAnalysis


class LLMError(Exception):
    pass


def complete_json(
    *,
    model: str,
    messages: list[dict[str, str]],
    settings: Settings,
    temperature: float = 0.2,
) -> dict[str, Any]:
    _apply_provider_env(settings)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        # "timeout": 120,
    }

    if model.startswith("ollama/") and settings.ollama_api_base:
        kwargs["api_base"] = settings.ollama_api_base
    else:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = litellm.completion(**kwargs)
    except Exception as exc:  # LiteLLM raises many provider-specific types
        print("LiteLLM exception:", repr(exc))
        raise LLMError(_friendly_llm_error(model, exc)) from exc

    try:
        content = response.choices[0].message.content or ""
    except (AttributeError, IndexError, KeyError) as exc:
        raise LLMError("The model returned an empty response.") from exc

    try:
        return _parse_json_payload(content)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LLMError("The model did not return valid JSON for the report.") from exc


def report_from_payload(
    payload: dict[str, Any],
    *,
    source_url: str,
    final_url: str,
    title: str | None,
    author: str | None,
    published: str | None,
    target_language: str,
    model: str,
    elapsed_seconds: float,
    char_count: int,
    truncated: bool,
) -> PageReport:
    analysis = payload.get("analysis") or {}
    return PageReport(
        source_url=source_url,
        final_url=final_url,
        title=payload.get("title") or title,
        author=author,
        published=published,
        target_language=target_language,
        model=model,
        elapsed_seconds=elapsed_seconds,
        char_count=char_count,
        truncated=truncated,
        translation=str(payload.get("translation") or ""),
        analysis=ContentAnalysis(
            key_claims=list(analysis.get("key_claims") or []),
            entities=list(analysis.get("entities") or []),
            topics=list(analysis.get("topics") or []),
            tone=str(analysis.get("tone") or ""),
            caveats=list(analysis.get("caveats") or []),
        ),
        summary=str(payload.get("summary") or ""),
        summary_bullets=list(payload.get("summary_bullets") or []),
    )


def _apply_provider_env(settings: Settings) -> None:
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    if settings.gemini_api_key:
        os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)
        os.environ.setdefault("GOOGLE_API_KEY", settings.gemini_api_key)
    if settings.ollama_api_base:
        os.environ.setdefault("OLLAMA_API_BASE", settings.ollama_api_base)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no json object")
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("json root must be an object")
    return data


def _friendly_llm_error(model: str, exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return (
            f"Authentication failed for `{model}`. Set the matching key in `.env` "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY)."
        )
    if "connection" in lowered or "connect" in lowered:
        if model.startswith("ollama/"):
            return (
                f"Could not reach Ollama for `{model}`. Start Ollama and pull the tag "
                "(for example `ollama pull llama3.2`)."
            )
        return f"Could not reach the provider for `{model}`."
    return f"Model call failed ({model}): {message}"
