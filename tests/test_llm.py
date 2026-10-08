from website_summarizer.config import Settings
from website_summarizer.ingest import ExtractedPage
from website_summarizer.llm import complete_json
from website_summarizer.models import PageReport
from website_summarizer.tasks import build_messages, run_report


def test_build_messages_include_three_tasks() -> None:
    page = ExtractedPage(
        url="https://harbor.example/lanterns",
        final_url="https://harbor.example/lanterns",
        html="<p>unused</p>",
        text="The city restored 40 copper lanterns along Pier 4.",
        title="Harbor lanterns",
        author="Mina Cole",
        published="2024-03-12",
        truncated=False,
        char_count=52,
    )
    messages = build_messages(page, "vi")
    blob = "\n".join(item["content"] for item in messages)
    assert "Translation" in blob
    assert "Analysis" in blob
    assert "Summary" in blob
    assert "Vietnamese" in blob
    assert "copper lanterns" in blob


def test_run_report_with_mocked_completion(monkeypatch) -> None:
    payload = {
        "title": "Harbor lanterns return to Pier 4",
        "translation": "The city restored forty lanterns.",
        "summary": "Pier 4 lighting is back after corrosion damage.",
        "summary_bullets": ["40 lanterns restored", "Fog boarding was slower"],
        "analysis": {
            "key_claims": ["Replicas follow the 1912 pattern"],
            "entities": ["Pier 4", "Mina Cole"],
            "topics": ["infrastructure", "harbor"],
            "tone": "neutral reporting",
            "caveats": ["Raw incident log was not released"],
        },
    }

    def fake_complete_json(**kwargs):
        assert kwargs["model"] == "ollama/llama3.2"
        return payload

    monkeypatch.setattr("website_summarizer.tasks.complete_json", fake_complete_json)
    page = ExtractedPage(
        url="https://harbor.example/lanterns",
        final_url="https://harbor.example/lanterns",
        html="",
        text="article",
        title="Harbor lanterns return to Pier 4",
        author="Mina Cole",
        published=None,
        truncated=False,
        char_count=7,
    )
    report = run_report(
        page,
        language_code="en",
        model="ollama/llama3.2",
        settings=Settings(),
        elapsed_seconds=1.25,
    )
    assert isinstance(report, PageReport)
    assert "40 lanterns" in report.summary_bullets[0]
    assert "incident log" in report.analysis.caveats[0]
    markdown = report.to_markdown()
    assert "# Harbor lanterns return to Pier 4" in markdown
    assert "ollama/llama3.2" in markdown


def test_complete_json_parses_fenced_payload(monkeypatch) -> None:
    class Message:
        content = '```json\n{"ok": true, "n": 1}\n```'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    monkeypatch.setattr("website_summarizer.llm.litellm.completion", lambda **kwargs: Response())
    data = complete_json(
        model="ollama/llama3.2",
        messages=[{"role": "user", "content": "hi"}],
        settings=Settings(),
    )
    assert data == {"ok": True, "n": 1}
