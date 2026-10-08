from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_api_base: str = "http://127.0.0.1:11434"
    default_model: str = "openai/gpt-4o-mini"
    ollama_model: str = "ollama/llama3.2"
    available_models: str = (
        "openai/gpt-4o-mini,"
        "anthropic/claude-3-5-haiku-latest,"
        "gemini/gemini-2.0-flash,"
        "ollama/llama3.2"
    )
    max_extract_chars: int = 24_000
    fetch_timeout_ms: int = 30_000
    playwright_browser: Literal["chromium", "firefox", "webkit"] = "firefox"

    def model_choices(self) -> list[str]:
        choices = [item.strip() for item in self.available_models.split(",") if item.strip()]
        for extra in (self.default_model, self.ollama_model):
            if extra and extra not in choices:
                choices.append(extra)
        return choices


def load_settings() -> Settings:
    return Settings()
