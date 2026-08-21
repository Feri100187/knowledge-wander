"""Public book domain models shared by search, recommendation, and Agent flows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


BookSource = Literal["openlibrary", "google_books"]


class PublicBook(BaseModel):
    """Normalized public metadata for one book."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=180)
    source: BookSource
    source_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=20)
    publisher: str | None = Field(default=None, max_length=300)
    published_date: str | None = Field(default=None, max_length=80)
    publication_year: str | None = Field(default=None, max_length=4)
    isbn_10: str | None = Field(default=None, max_length=20)
    isbn_13: str | None = Field(default=None, max_length=20)
    subjects: list[str] = Field(default_factory=list, max_length=30)
    description: str | None = Field(default=None, max_length=6000)
    language: str | None = Field(default=None, max_length=40)
    cover_url: str | None = Field(default=None, max_length=1000)
    info_url: str | None = Field(default=None, max_length=1000)
    preview_url: str | None = Field(default=None, max_length=1000)

    @field_validator("authors", "subjects", mode="before")
    @classmethod
    def clean_text_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]


class BookRecommendation(PublicBook):
    """A public book ranked for the current knowledge path."""

    reason: str = Field(min_length=1, max_length=600)
    relevance_score: float = Field(ge=0.0, le=1.0)


class BookRecommendRequest(BaseModel):
    """Knowledge-path context used to find related public books."""

    model_config = ConfigDict(extra="forbid")

    root_topic: str = Field(min_length=1, max_length=120)
    node_label: str = Field(min_length=1, max_length=80)
    node_domain: str = Field(min_length=1, max_length=80)
    surprise_level: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str | None = Field(default=None, max_length=20)

    @field_validator("root_topic", "node_label", "node_domain", "language", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class BookRecommendResponse(BaseModel):
    """Recommendation response backed only by public book metadata."""

    model_config = ConfigDict(extra="forbid")

    data_source: str = "public_api"
    data_notice: str
    query: str
    books: list[BookRecommendation] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


class BookSearchResponse(BaseModel):
    """Normalized public-book search response."""

    model_config = ConfigDict(extra="forbid")

    data_source: str = "public_api"
    query: str
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=20)
    total: int = Field(ge=0)
    books: list[PublicBook] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None
