from fastapi.testclient import TestClient

from website_summarizer.web import app

client = TestClient(app)


def test_home_renders_form() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Public URL" in response.text
    assert "Analyze page" in response.text


def test_invalid_url_shows_error() -> None:
    response = client.post(
        "/analyze",
        data={"url": "ftp://example.com", "language": "en", "model": "openai/gpt-4o-mini"},
    )
    assert response.status_code == 400
    assert "public http(s) URL" in response.text


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}
