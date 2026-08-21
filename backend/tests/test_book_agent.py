"""Tests for the public-book Tool Calling Agent and safe SSE events."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import books as books_api
from app.main import app
from app.models.book import BookRecommendResponse, BookRecommendation, BookSearchResponse, PublicBook
from app.models.book_agent import BookAgentRequest, BookAgentResponse, SearchBooksToolArgs
from app.services.book_agent import BOOK_AGENT_SYSTEM_PROMPT, SEARCH_BOOKS_TOOL, BookAgent
from app.services.book_errors import BookServiceError


def run(awaitable: Any) -> Any:
    return asyncio.run(awaitable)


def book(book_id: str = "book-1", title: str = "程序化叙事设计") -> PublicBook:
    return PublicBook(
        id=book_id,
        source="openlibrary",
        source_id=f"/works/{book_id}",
        title=title,
        authors=["真实作者"],
        publisher="真实出版社",
        published_date="2024",
        publication_year="2024",
        isbn_10=None,
        isbn_13=None,
        subjects=["叙事"],
        description="公开数据源返回的简介。",
        language="zh",
        cover_url=None,
        info_url=f"https://openlibrary.org/works/{book_id}",
        preview_url=None,
    )


def search(query: str, books: list[PublicBook]) -> BookSearchResponse:
    return BookSearchResponse(
        query=query,
        page=1,
        page_size=8,
        total=len(books),
        books=books,
    )


def recommendation_response(item: PublicBook) -> BookRecommendResponse:
    recommendation = BookRecommendation(
        **item.model_dump(),
        reason="与当前知识路径相连。",
        relevance_score=0.8,
    )
    return BookRecommendResponse(
        data_source="public_api",
        data_notice="公开书目元数据。",
        query="程序化叙事",
        books=[recommendation],
    )


def request() -> BookAgentRequest:
    return BookAgentRequest(
        root_topic="游戏开发",
        node_label="程序化叙事",
        node_domain="游戏设计",
        current_path=["游戏开发", "交互叙事", "程序化叙事"],
        surprise_level=0.65,
    )


def tool_response(call_id: str, query: str) -> dict[str, Any]:
    return {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "search_books",
                        "arguments": json.dumps({"query": query, "limit": 8}),
                    },
                }],
            },
        }],
    }


def final_response(*recommendations: dict[str, str]) -> dict[str, Any]:
    return {
        "choices": [{
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": json.dumps({
                    "summary": "沿当前知识路径找到公开书目。",
                    "recommendations": list(recommendations),
                }, ensure_ascii=False),
            },
        }],
    }


class FakeLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    async def chat_completion(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((list(messages), kwargs))
        return self.responses.pop(0)


class FakeBookService:
    def __init__(self, responses: dict[str, BookSearchResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def search_books(self, query: str, **kwargs: Any) -> BookSearchResponse:
        self.calls.append({"query": query, **kwargs})
        return self.responses.get(query, search(query, []))

    async def recommend_books(self, _request: Any) -> BookRecommendResponse:
        item = next(iter(self.responses.values())).books[0] if self.responses else book("fallback")
        return recommendation_response(item)


def test_agent_executes_search_books_and_only_returns_verified_ids() -> None:
    real_book = book()
    llm = FakeLLM([
        tool_response("call-1", "程序化叙事"),
        final_response({"book_id": real_book.id, "reason": "题名连接当前路径。"}),
    ])
    service = FakeBookService({"程序化叙事": search("程序化叙事", [real_book])})

    response = run(BookAgent(llm_service=llm, book_service=service).discover(request()))

    assert response.mode == "agent"
    assert response.tool_calls == 1
    assert response.books[0].book.id == real_book.id
    assert llm.calls[0][1]["tools"] == [SEARCH_BOOKS_TOOL]
    assert llm.calls[0][1]["tool_choice"] == "auto"
    assert llm.calls[1][0][-1]["role"] == "tool"
    assert "程序化叙事设计" in llm.calls[1][0][-1]["content"]


def test_unknown_final_id_is_discarded_and_prompt_requires_verified_selection() -> None:
    real_book = book()
    llm = FakeLLM([
        tool_response("call-1", "程序化叙事"),
        final_response(
            {"book_id": "not-returned", "reason": "不应出现。"},
            {"book_id": real_book.id, "reason": "来自工具结果。"},
        ),
    ])
    service = FakeBookService({"程序化叙事": search("程序化叙事", [real_book])})

    response = run(BookAgent(llm_service=llm, book_service=service).discover(request()))

    assert [item.book.id for item in response.books] == [real_book.id]
    assert "所有具体书名、作者、ISBN" in BOOK_AGENT_SYSTEM_PROMPT
    assert "第一次已有足够结果时不要继续第二次检索" in BOOK_AGENT_SYSTEM_PROMPT
    assert "不要为了近义词" in BOOK_AGENT_SYSTEM_PROMPT


def test_agent_has_two_tool_call_limit_and_no_more() -> None:
    first = book("book-1", "第一本书")
    second = book("book-2", "第二本书")
    llm = FakeLLM([
        tool_response("call-1", "第一次"),
        tool_response("call-2", "第二次"),
        final_response({"book_id": second.id, "reason": "第二次结果。"}),
    ])
    service = FakeBookService({
        "第一次": search("第一次", [first]),
        "第二次": search("第二次", [second]),
    })

    response = run(BookAgent(llm_service=llm, book_service=service).discover(request()))

    assert response.tool_calls == 2
    assert len(service.calls) == 2
    assert len(llm.calls) == 3
    assert "tools" not in llm.calls[-1][1]


def test_book_source_error_propagates_without_agent_inventing_data() -> None:
    llm = FakeLLM([tool_response("call-1", "程序化叙事")])

    class FailingService(FakeBookService):
        async def search_books(self, query: str, **kwargs: Any) -> BookSearchResponse:
            self.calls.append({"query": query, **kwargs})
            raise BookServiceError("BOOK_SOURCE_UNAVAILABLE")

    with pytest.raises(BookServiceError) as caught:
        run(BookAgent(llm_service=llm, book_service=FailingService({})).discover(request()))
    assert caught.value.code == "BOOK_SOURCE_UNAVAILABLE"


def test_fallback_uses_same_public_service() -> None:
    real_book = book("fallback", "稳定公开书目")
    llm = FakeLLM([{"choices": [{"message": {"content": "not json"}}]}])
    service = FakeBookService({"程序化叙事": search("程序化叙事", [real_book])})

    response = run(BookAgent(llm_service=llm, book_service=service).discover(request()))

    assert response.mode == "fallback"
    assert response.fallback_used is True
    assert response.books[0].book.id == real_book.id


def test_tool_schema_rejects_old_or_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SearchBooksToolArgs.model_validate({"query": "Python", "campus": "old"})
    with pytest.raises(ValidationError):
        SearchBooksToolArgs.model_validate({"query": "Python", "limit": 11})


def test_agent_stream_route_emits_safe_public_events(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubAgent:
        async def discover(self, _request: BookAgentRequest, on_event=None) -> BookAgentResponse:
            await on_event({"type": "agent_started"})
            await on_event({"type": "tool_call", "tool": "search_books", "query": "程序化叙事"})
            await on_event({"type": "tool_result", "query": "程序化叙事", "result_count": 8, "duration_ms": 1420})
            await on_event({"type": "complete", "summary": "完成。", "metrics": {
                "mode": "agent",
                "tool_used": True,
                "queries": ["程序化叙事"],
                "tool_trace": [],
                "tool_calls": 1,
                "tool_latency_ms": 1420,
                "llm_rounds": 2,
                "agent_total_latency_ms": 1800,
                "fallback_used": False,
            }})
            return BookAgentResponse(mode="agent", tool_used=True, summary="完成。")

    monkeypatch.setattr(books_api, "BookAgent", StubAgent)
    response = TestClient(app).post(
        "/api/books/agent/discover/stream",
        json={
            "root_topic": "游戏开发",
            "node_label": "程序化叙事",
            "node_domain": "游戏设计",
            "current_path": ["游戏开发", "程序化叙事"],
        },
    )

    assert response.status_code == 200
    assert "event: tool_call" in response.text
    assert '"tool": "search_books"' in response.text
    assert '"result_count": 8' in response.text
    assert "Authorization" not in response.text
    assert "Cookie" not in response.text
