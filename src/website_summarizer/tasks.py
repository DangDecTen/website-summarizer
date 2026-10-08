from __future__ import annotations

from website_summarizer.config import Settings
from website_summarizer.ingest import ExtractedPage
from website_summarizer.llm import complete_json, report_from_payload
from website_summarizer.models import PageReport

LANGUAGE_LABELS = {
    "en": "English",
    "vi": "Vietnamese",
}

REPORT_JSON_INSTRUCTIONS = """
Return a single JSON object with exactly these keys:
{
  "title": "page title in the target language if you can, else original",
  "translation": "faithful translation of the extracted article into the target language",
  "summary": "a short narrative summary in the target language (1-3 paragraphs)",
  "summary_bullets": ["3 to 7 key points in the target language"],
  "analysis": {
    "key_claims": ["factual or rhetorical claims the page makes"],
    "entities": ["people, orgs, products, places"],
    "topics": ["short topic labels"],
    "tone": "one short phrase (e.g. 'neutral reporting', 'promotional')",
    "caveats": ["what is missing, uncertain, one-sided, or not evidenced"]
  }
}
Do not wrap the JSON in markdown. Do not invent facts that are not in the article.
""".strip()


def language_name(code: str) -> str:
    return LANGUAGE_LABELS.get(code, code)


def translate_instructions(language: str) -> str:
    return (
        f"Translate the extracted article into {language}. "
        "Keep names, numbers, and quotes accurate. If the text was truncated, translate what remains."
    )


def analyze_instructions(language: str) -> str:
    return (
        f"Analyze the extracted article in {language}. "
        "Separate claims from evidence. Flag missing context, marketing language, and uncertainty."
    )


def summarize_instructions(language: str) -> str:
    return (
        f"Summarize the extracted article in {language} for a busy reader. "
        "Lead with what the page is and why it matters, then the main points."
    )


def build_messages(page: ExtractedPage, language_code: str) -> list[dict[str, str]]:
    language = language_name(language_code)
    metadata_lines = [
        f"URL: {page.final_url or page.url}",
        f"Title: {page.title or '(unknown)'}",
        f"Author: {page.author or '(unknown)'}",
        f"Published: {page.published or '(unknown)'}",
        f"Truncated: {'yes' if page.truncated else 'no'}",
    ]
    user = "\n".join(
        [
            f"Target language: {language} ({language_code})",
            "",
            "You will perform three tasks on ONE public web page:",
            f"1. Translation — {translate_instructions(language)}",
            f"2. Analysis — {analyze_instructions(language)}",
            f"3. Summary — {summarize_instructions(language)}",
            "",
            REPORT_JSON_INSTRUCTIONS,
            "",
            "Page metadata:",
            *metadata_lines,
            "",
            "Extracted article:",
            page.text,
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a careful web-page analyst. You only use the extracted article. "
                "You never browse, log in, or fetch extra URLs. "
                "Write every user-facing field in the requested target language."
            ),
        },
        {"role": "user", "content": user},
    ]


def run_report(
    page: ExtractedPage,
    *,
    language_code: str,
    model: str,
    settings: Settings,
    elapsed_seconds: float,
) -> PageReport:
    payload = complete_json(
        model=model,
        messages=build_messages(page, language_code),
        settings=settings,
    )
    return report_from_payload(
        payload,
        source_url=page.url,
        final_url=page.final_url,
        title=page.title,
        author=page.author,
        published=page.published,
        target_language=language_name(language_code),
        model=model,
        elapsed_seconds=elapsed_seconds,
        char_count=page.char_count,
        truncated=page.truncated,
    )
