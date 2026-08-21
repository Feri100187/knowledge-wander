"""Bounded Tool Calling Agent for verified public books."""

from __future__ import annotations

import inspect
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.models.book import BookRecommendRequest, BookSearchResponse, PublicBook
from app.models.book_agent import (
    BookAgentBook,
    BookAgentFinalOutput,
    BookAgentRequest,
    BookAgentResponse,
    BookAgentToolTrace,
    SearchBooksToolArgs,
)
from app.services.book_errors import BookServiceError
from app.services.public_book_service import get_book_service
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 2
MAX_TOOL_BOOKS = 10
MAX_DESCRIPTION_LENGTH = 600
ProgressSink = Callable[[dict[str, Any]], Awaitable[None] | None]

SEARCH_BOOKS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_books",
        "description": (
            "Search verified book metadata from public book databases. "
            "Use concise titles, concepts, subjects, or author names."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concise public book search keyword.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                },
                "language": {
                    "type": "string",
                    "description": "Optional ISO language preference.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}

BOOK_AGENT_SYSTEM_PROMPT = """你是 Knowledge Wander 的公开图书探索智能体。

你的目标不是凭记忆推荐书，而是根据用户当前知识路径调用 search_books，检索真实的公开图书数据库元数据。

规则：
1. 所有具体书名、作者、ISBN、出版社、出版年份和简介必须来自 search_books 工具结果。
2. 不得凭记忆虚构书目，不得把工具没有返回的信息补写成事实。
3. 搜索词应简洁，优先使用当前知识概念（通常是 2~12 个汉字或必要的英文术语），不要搜索完整自然语言问题。
4. 根据 root topic、node、domain 和 current path 判断最有效的检索概念。
5. 最多调用 search_books 两次。第一次返回 0~2 条候选，或结果明显与当前知识节点不相关时，才使用第二次。
6. 第一次已有足够结果时不要继续第二次检索；如果第一次已经返回 >=5 条合适的真实书目，应直接从现有结果完成推荐，不要为了近义词、覆盖率或“看看有没有更好结果”再次检索。
7. 对中文概念，search_books 会在后台生成英文检索词，并且只向公开图书数据库发送英文 query；一次工具调用内部可能使用一个英文 fallback，但这不算新的工具调用。不要为了英文版本另行调用 search_books。
8. 禁止对完全相同的 query 重复调用 search_books；如果确实需要第二次搜索，必须换成语义不同的概念，而不是原 query 的重复提交。
9. 最终只从已验证的 book id 中选择最多 4 本书。
10. 面向用户的 summary 和 reason 继续使用中文；书名、作者等真实书目元数据保持工具返回的原文。

最终只输出 JSON：
{"summary":"...","recommendations":[{"book_id":"真实工具结果中的 ID","reason":"..."}]}

reason 只能解释书为什么值得沿当前知识路径阅读，或为什么形成有意思的知识跳跃。不要输出隐藏思考过程。"""

FINAL_JSON_INSTRUCTION = (
    "现在只返回严格 JSON，不要 Markdown 或其他文字。字段必须是 summary 和 "
    "recommendations；每个 recommendation 只能包含 book_id 和 reason。"
)


def _normalize_tool_query(value: str) -> str:
    return " ".join(value.casefold().split())


class BookAgent:
    """A bounded two-round loop around the safe search_books function tool."""

    def __init__(self, llm_service: Any | None = None, book_service: Any | None = None) -> None:
        self._llm_service = llm_service
        self._book_service = book_service

    def _get_book_service(self) -> Any:
        return self._book_service if self._book_service is not None else get_book_service()

    async def discover(
        self,
        request: BookAgentRequest,
        on_event: ProgressSink | None = None,
    ) -> BookAgentResponse:
        started_at = time.perf_counter()
        logger.info("Book Agent started")
        await self._emit(on_event, {"type": "agent_started"})
        await self._emit(on_event, {"type": "path", "path": request.current_path})
        llm = self._llm_service if self._llm_service is not None else get_llm_service()
        if llm is None:
            return await self._fallback(request, started_at, llm_rounds=0, on_event=on_event)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": BOOK_AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "root_topic": request.root_topic,
                        "node_label": request.node_label,
                        "node_domain": request.node_domain,
                        "current_path": request.current_path,
                        "surprise_level": request.surprise_level,
                        "language": request.language,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        valid_books: dict[str, PublicBook] = {}
        traces: list[BookAgentToolTrace] = []
        queries: list[str] = []
        tool_results_by_query: dict[str, BookSearchResponse | BookServiceError] = {}
        llm_rounds = 0
        tool_rounds = 0

        while tool_rounds < MAX_TOOL_ROUNDS:
            try:
                raw_response = await llm.chat_completion(
                    messages,
                    tools=[SEARCH_BOOKS_TOOL],
                    tool_choice="auto",
                )
            except Exception as exc:
                logger.warning("Book Agent LLM unavailable; using fallback error=%s", type(exc).__name__)
                return await self._fallback(
                    request,
                    started_at,
                    llm_rounds=llm_rounds,
                    on_event=on_event,
                )

            llm_rounds += 1
            try:
                message = self._extract_message(raw_response)
                tool_calls = self._extract_tool_calls(message)
            except ValueError as exc:
                logger.warning("Book Agent response protocol invalid reason=%s", str(exc))
                return await self._fallback(
                    request,
                    started_at,
                    llm_rounds=llm_rounds,
                    on_event=on_event,
                )

            if tool_calls is None:
                if tool_rounds == 0:
                    return await self._fallback(
                        request,
                        started_at,
                        llm_rounds=llm_rounds,
                        on_event=on_event,
                    )
                final_output = self._parse_final_output(message)
                if final_output is not None:
                    response = self._build_agent_response(
                        final_output,
                        valid_books,
                        queries,
                        traces,
                        llm_rounds,
                        started_at,
                    )
                    await self._emit_response_events(response, on_event)
                    return response
                break

            remaining_calls = MAX_TOOL_ROUNDS - len(traces)
            if len(tool_calls) > remaining_calls:
                return await self._fallback(
                    request,
                    started_at,
                    llm_rounds=llm_rounds,
                    on_event=on_event,
                )

            messages.append(message)
            for tool_call in tool_calls:
                try:
                    call_id, args = self._parse_tool_call(tool_call)
                except (ValueError, ValidationError) as exc:
                    logger.warning("Book Agent tool call validation failed reason=%s", type(exc).__name__)
                    return await self._fallback(
                        request,
                        started_at,
                        llm_rounds=llm_rounds,
                        on_event=on_event,
                    )

                await self._emit(
                    on_event,
                    {"type": "tool_call", "tool": "search_books", "query": args.query},
                )
                normalized_query = _normalize_tool_query(args.query)
                cached_tool_result = tool_results_by_query.get(normalized_query)
                if isinstance(cached_tool_result, BookServiceError):
                    logger.info(
                        "Book Agent reused failed search_books result query_length=%d code=%s",
                        len(args.query),
                        cached_tool_result.code,
                    )
                    raise cached_tool_result

                if cached_tool_result is not None:
                    logger.info(
                        "Book Agent reused search_books result query_length=%d",
                        len(args.query),
                    )
                    normalized_result = cached_tool_result.model_copy(deep=True)
                    duration_ms = 0.0
                else:
                    tool_started_at = time.perf_counter()
                    try:
                        search_result = await self._get_book_service().search_books(
                            args.query,
                            page=1,
                            limit=args.limit,
                            language=args.language,
                        )
                        normalized_result = (
                            search_result
                            if isinstance(search_result, BookSearchResponse)
                            else BookSearchResponse.model_validate(search_result)
                        )
                    except BookServiceError as error:
                        tool_results_by_query[normalized_query] = error
                        raise
                    except ValidationError as exc:
                        error = BookServiceError("INVALID_RESPONSE")
                        tool_results_by_query[normalized_query] = error
                        raise error from exc
                    tool_results_by_query[normalized_query] = normalized_result
                    duration_ms = (time.perf_counter() - tool_started_at) * 1000

                if not any(
                    _normalize_tool_query(query) == normalized_query
                    for query in queries
                ):
                    queries.append(args.query)
                trace = BookAgentToolTrace(
                    tool="search_books",
                    query=args.query,
                    language=args.language,
                    result_count=len(normalized_result.books),
                    duration_ms=round(duration_ms, 2),
                )
                traces.append(trace)
                await self._emit(
                    on_event,
                    {
                        "type": "tool_result",
                        "query": args.query,
                        "result_count": len(normalized_result.books),
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                for book in normalized_result.books[:MAX_TOOL_BOOKS]:
                    valid_books[book.id] = book
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": "search_books",
                        "content": json.dumps(
                            self._compress_tool_result(args.query, normalized_result),
                            ensure_ascii=False,
                        ),
                    }
                )
            tool_rounds += 1

        messages.append({"role": "system", "content": FINAL_JSON_INSTRUCTION})
        final_kwargs: dict[str, Any] = {}
        config = getattr(llm, "config", None)
        if getattr(config, "json_mode", False):
            final_kwargs["response_format"] = {"type": "json_object"}
        try:
            final_response = await llm.chat_completion(messages, **final_kwargs)
            llm_rounds += 1
            final_output = self._parse_final_output(self._extract_message(final_response))
        except Exception as exc:
            logger.warning("Book Agent final response unavailable; using fallback error=%s", type(exc).__name__)
            return await self._fallback(
                request,
                started_at,
                llm_rounds=llm_rounds,
                on_event=on_event,
            )

        if final_output is None:
            return await self._fallback(
                request,
                started_at,
                llm_rounds=llm_rounds,
                on_event=on_event,
            )
        response = self._build_agent_response(
            final_output,
            valid_books,
            queries,
            traces,
            llm_rounds,
            started_at,
        )
        await self._emit_response_events(response, on_event)
        return response

    @staticmethod
    async def _emit(on_event: ProgressSink | None, event: dict[str, Any]) -> None:
        if on_event is None:
            return
        try:
            result = on_event(event)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # pragma: no cover - defensive stream isolation
            logger.debug("Book Agent progress sink unavailable error=%s", type(exc).__name__)

    @classmethod
    async def _emit_response_events(
        cls,
        response: BookAgentResponse,
        on_event: ProgressSink | None,
    ) -> None:
        await cls._emit(on_event, {"type": "final_selection", "book_count": len(response.books)})
        for item in response.books:
            await cls._emit(
                on_event,
                {"type": "book", "book": item.book.model_dump(), "reason": item.reason},
            )
        await cls._emit(
            on_event,
            {
                "type": "complete",
                "summary": response.summary,
                "metrics": {
                    "mode": response.mode,
                    "tool_used": response.tool_used,
                    "queries": response.queries,
                    "tool_trace": [trace.model_dump() for trace in response.tool_trace],
                    "tool_calls": response.tool_calls,
                    "tool_latency_ms": response.tool_latency_ms,
                    "llm_rounds": response.llm_rounds,
                    "agent_total_latency_ms": response.agent_total_latency_ms,
                    "fallback_used": response.fallback_used,
                },
            },
        )

    @staticmethod
    def _extract_message(response: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise ValueError("response is not an object")
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("choices is missing")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("message is missing")
        return message

    @staticmethod
    def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]] | None:
        if "tool_calls" not in message:
            return None
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list) or not tool_calls:
            raise ValueError("tool_calls is malformed")
        if not all(isinstance(tool_call, dict) for tool_call in tool_calls):
            raise ValueError("tool_calls item is malformed")
        return tool_calls

    @staticmethod
    def _parse_tool_call(tool_call: dict[str, Any]) -> tuple[str, SearchBooksToolArgs]:
        call_id = tool_call.get("id")
        function = tool_call.get("function")
        if not isinstance(call_id, str) or not call_id.strip():
            raise ValueError("tool call id is missing")
        if not isinstance(function, dict) or function.get("name") != "search_books":
            raise ValueError("unknown tool")
        raw_arguments = function.get("arguments")
        if isinstance(raw_arguments, str):
            try:
                raw_arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise ValueError("tool arguments are not JSON") from exc
        if not isinstance(raw_arguments, dict):
            raise ValueError("tool arguments are not an object")
        return call_id, SearchBooksToolArgs.model_validate(raw_arguments)

    @staticmethod
    def _compress_tool_result(query: str, result: BookSearchResponse) -> dict[str, Any]:
        return {
            "query": query,
            "total": result.total,
            "books": [
                {
                    "id": book.id,
                    "source": book.source,
                    "source_id": book.source_id,
                    "title": book.title,
                    "authors": book.authors,
                    "publisher": book.publisher,
                    "published_date": book.published_date,
                    "publication_year": book.publication_year,
                    "isbn_10": book.isbn_10,
                    "isbn_13": book.isbn_13,
                    "subjects": book.subjects,
                    "description": (book.description or "")[:MAX_DESCRIPTION_LENGTH] or None,
                    "language": book.language,
                    "cover_url": book.cover_url,
                    "info_url": book.info_url,
                    "preview_url": book.preview_url,
                }
                for book in result.books[:MAX_TOOL_BOOKS]
            ],
        }

    @staticmethod
    def _parse_final_output(message: dict[str, Any]) -> BookAgentFinalOutput | None:
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        cleaned = content.strip()
        code_block = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if code_block:
            cleaned = code_block.group(1).strip()
        try:
            return BookAgentFinalOutput.model_validate(json.loads(cleaned))
        except (json.JSONDecodeError, ValidationError):
            return None

    async def _fallback(
        self,
        request: BookAgentRequest,
        started_at: float,
        *,
        llm_rounds: int,
        on_event: ProgressSink | None,
    ) -> BookAgentResponse:
        result = await self._get_book_service().recommend_books(
            BookRecommendRequest(
                root_topic=request.root_topic,
                node_label=request.node_label,
                node_domain=request.node_domain,
                surprise_level=request.surprise_level,
                language=request.language,
            )
        )
        books = [
            BookAgentBook(
                book=PublicBook(**book.model_dump(exclude={"reason", "relevance_score"})),
                reason=book.reason,
            )
            for book in result.books[:4]
        ]
        response = BookAgentResponse(
            mode="fallback",
            tool_used=False,
            summary=(
                "已使用稳定的公开图书推荐模式，返回与当前知识节点相关的书目。"
                if books
                else result.message or "暂未找到相关公开图书。"
            ),
            queries=[result.query] if result.query else [],
            books=books,
            llm_rounds=llm_rounds,
            agent_total_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            fallback_used=True,
        )
        await self._emit_response_events(response, on_event)
        return response

    @staticmethod
    def _build_agent_response(
        final_output: BookAgentFinalOutput,
        valid_books: dict[str, PublicBook],
        queries: list[str],
        traces: list[BookAgentToolTrace],
        llm_rounds: int,
        started_at: float,
    ) -> BookAgentResponse:
        selected: list[BookAgentBook] = []
        selected_ids: set[str] = set()
        for recommendation in final_output.recommendations:
            book = valid_books.get(recommendation.book_id)
            if book is None or book.id in selected_ids:
                continue
            selected.append(BookAgentBook(book=book, reason=recommendation.reason))
            selected_ids.add(book.id)
            if len(selected) >= 4:
                break
        return BookAgentResponse(
            mode="agent",
            tool_used=True,
            summary=final_output.summary,
            queries=queries[:2],
            books=selected,
            tool_trace=traces[:2],
            tool_calls=len(traces),
            tool_latency_ms=round(sum(trace.duration_ms or 0.0 for trace in traces), 2),
            llm_rounds=llm_rounds,
            agent_total_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            fallback_used=False,
        )
