"""Tests for retrieval-only English book search terms."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.book_search_query import BookSearchQueryBuilder


def run(awaitable: Any) -> Any:
    return asyncio.run(awaitable)


class FakeLLM:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[list[dict[str, Any]]] = []

    async def chat_completion(self, messages: list[dict[str, Any]], **_kwargs: Any) -> dict[str, Any]:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return {
            "choices": [{"message": {"content": self.content}}],
        }


def test_chinese_term_is_generated_and_cached() -> None:
    llm = FakeLLM("criminal psychology\n不要解释")
    builder = BookSearchQueryBuilder(llm, cache_ttl_seconds=2700, cache_max_entries=2)

    first = run(builder.build("犯罪心理学"))
    second = run(builder.build("  犯罪心理学  "))

    assert first.original_query == "犯罪心理学"
    assert first.english_query == "criminal psychology"
    assert second == first
    assert len(llm.calls) == 1


def test_english_query_skips_translation() -> None:
    llm = FakeLLM("should not be called")
    terms = run(BookSearchQueryBuilder(llm).build("machine learning"))

    assert terms.original_query == "machine learning"
    assert terms.primary_english_query == "machine learning"
    assert terms.english_query == "machine learning"
    assert terms.fallback_english_query is None
    assert llm.calls == []


def test_primary_and_optional_fallback_terms_are_normalized() -> None:
    llm = FakeLLM("game level design\ngame design")

    terms = run(BookSearchQueryBuilder(llm).build("游戏关卡策划"))

    assert terms.primary_english_query == "game level design"
    assert terms.fallback_english_query == "game design"


def test_invalid_or_failed_generation_returns_no_english_term() -> None:
    invalid = FakeLLM("books about criminal psychology")
    failed = FakeLLM(error=TimeoutError("llm timeout"))

    invalid_terms = run(BookSearchQueryBuilder(invalid).build("犯罪心理学"))
    failed_terms = run(BookSearchQueryBuilder(failed).build("犯罪心理学"))

    assert invalid_terms.primary_english_query is None
    assert invalid_terms.fallback_english_query is None
    assert failed_terms.primary_english_query is None
    assert failed_terms.fallback_english_query is None


def test_unconfigured_llm_does_not_fall_back_to_chinese_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.book_search_query.get_llm_service", lambda: None)

    terms = run(BookSearchQueryBuilder().build("机器学习"))

    assert terms.original_query == "机器学习"
    assert terms.primary_english_query is None
    assert terms.fallback_english_query is None
