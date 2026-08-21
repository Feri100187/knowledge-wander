"""Schemas for the public-book Tool Calling Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.book import PublicBook


class SearchBooksToolArgs(BaseModel):
    """Strict arguments exposed to the LLM search_books tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=8, ge=1, le=10)
    language: str | None = Field(default=None, max_length=20)

    @field_validator("query", "language", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("query")
    @classmethod
    def require_query(cls, value: str | None) -> str:
        if not value:
            raise ValueError("query must not be empty")
        return value


class BookAgentRequest(BaseModel):
    """Knowledge-path context supplied to the public-book Agent."""

    model_config = ConfigDict(extra="forbid")

    root_topic: str = Field(min_length=1, max_length=120)
    node_label: str = Field(min_length=1, max_length=80)
    node_domain: str = Field(min_length=1, max_length=80)
    current_path: list[str] = Field(min_length=1, max_length=12)
    surprise_level: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str | None = Field(default=None, max_length=20)

    @field_validator("root_topic", "node_label", "node_domain", "language", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("current_path", mode="before")
    @classmethod
    def strip_path(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item.strip() if isinstance(item, str) else item for item in value]


class BookAgentFinalRecommendation(BaseModel):
    """The final model can reference only a verified public-book ID."""

    model_config = ConfigDict(extra="forbid")

    book_id: str = Field(min_length=1, max_length=180)
    reason: str = Field(min_length=1, max_length=600)

    @field_validator("book_id", "reason", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class BookAgentFinalOutput(BaseModel):
    """Strict final JSON shape requested from the LLM."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1200)
    recommendations: list[BookAgentFinalRecommendation] = Field(max_length=4)

    @field_validator("summary", mode="before")
    @classmethod
    def strip_summary(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class BookAgentToolTrace(BaseModel):
    """Safe, user-visible tool metadata."""

    model_config = ConfigDict(extra="forbid")

    tool: Literal["search_books"]
    query: str = Field(min_length=1, max_length=100)
    language: str | None = Field(default=None, max_length=20)
    result_count: int = Field(ge=0, le=50)
    duration_ms: float | None = Field(default=None, ge=0.0)


class BookAgentBook(BaseModel):
    """An LLM explanation attached to a verified public book."""

    model_config = ConfigDict(extra="forbid")

    book: PublicBook
    reason: str = Field(min_length=1, max_length=600)


class BookAgentResponse(BaseModel):
    """Public response for the bounded public-book Agent."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["agent", "fallback"]
    tool_used: bool
    summary: str
    queries: list[str] = Field(default_factory=list, max_length=2)
    books: list[BookAgentBook] = Field(default_factory=list, max_length=4)
    tool_trace: list[BookAgentToolTrace] = Field(default_factory=list, max_length=2)
    tool_calls: int = Field(default=0, ge=0, le=2)
    tool_latency_ms: float = Field(default=0.0, ge=0.0)
    llm_rounds: int = Field(default=0, ge=0)
    agent_total_latency_ms: float = Field(default=0.0, ge=0.0)
    fallback_used: bool = False
