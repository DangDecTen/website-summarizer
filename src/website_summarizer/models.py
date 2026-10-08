from __future__ import annotations

from pydantic import BaseModel, Field


class ContentAnalysis(BaseModel):
    key_claims: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    tone: str = ""
    caveats: list[str] = Field(default_factory=list)


class PageReport(BaseModel):
    source_url: str
    final_url: str
    title: str | None = None
    author: str | None = None
    published: str | None = None
    target_language: str
    model: str
    elapsed_seconds: float
    char_count: int
    truncated: bool = False
    translation: str = ""
    analysis: ContentAnalysis = Field(default_factory=ContentAnalysis)
    summary: str = ""
    summary_bullets: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        bullets = "\n".join(f"- {item}" for item in self.summary_bullets) or "- _(none)_"
        claims = "\n".join(f"- {item}" for item in self.analysis.key_claims) or "- _(none)_"
        entities = ", ".join(self.analysis.entities) or "_(none)_"
        topics = ", ".join(self.analysis.topics) or "_(none)_"
        caveats = "\n".join(f"- {item}" for item in self.analysis.caveats) or "- _(none)_"
        truncated = "yes" if self.truncated else "no"
        return "\n".join(
            [
                f"# {self.title or 'Untitled page'}",
                "",
                f"- **Source:** {self.source_url}",
                f"- **Fetched URL:** {self.final_url}",
                f"- **Author:** {self.author or 'unknown'}",
                f"- **Published:** {self.published or 'unknown'}",
                f"- **Output language:** {self.target_language}",
                f"- **Model:** {self.model}",
                f"- **Elapsed:** {self.elapsed_seconds:.1f}s",
                f"- **Extracted chars:** {self.char_count} (truncated: {truncated})",
                "",
                "## Summary",
                "",
                self.summary.strip() or "_(empty)_",
                "",
                "### Key points",
                "",
                bullets,
                "",
                "## Analysis",
                "",
                f"**Tone:** {self.analysis.tone or 'unknown'}",
                "",
                f"**Entities:** {entities}",
                "",
                f"**Topics:** {topics}",
                "",
                "### Key claims",
                "",
                claims,
                "",
                "### What's missing / caveats",
                "",
                caveats,
                "",
                "## Translation",
                "",
                self.translation.strip() or "_(empty)_",
                "",
            ]
        )
