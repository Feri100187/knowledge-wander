"""Public book search, recommendation, and Agent routes."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.book import (
    BookRecommendRequest,
    BookRecommendResponse,
    BookSearchResponse,
)
from app.models.book_agent import BookAgentRequest, BookAgentResponse
from app.services.book_agent import BookAgent
from app.services.book_errors import BookServiceError
from app.services.public_book_service import get_book_service

router = APIRouter(tags=["books"])
logger = logging.getLogger(__name__)


def _raise_book_error(error: BookServiceError) -> None:
    raise HTTPException(
        status_code=error.http_status,
        detail={"code": error.code, "message": error.public_message},
    )


@router.get(
    "/books/search",
    response_model=BookSearchResponse,
    summary="Search public book metadata",
)
async def search_books(
    q: str = Query(min_length=1, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=20),
    language: str | None = Query(default=None, max_length=20),
) -> BookSearchResponse:
    try:
        return await get_book_service().search_books(
            q,
            page=page,
            limit=limit,
            language=language,
        )
    except BookServiceError as error:
        _raise_book_error(error)


@router.post(
    "/books/recommend",
    response_model=BookRecommendResponse,
    summary="Recommend public books for a knowledge node",
)
async def recommend_books(request: BookRecommendRequest) -> BookRecommendResponse:
    try:
        return await get_book_service().recommend_books(request)
    except BookServiceError as error:
        _raise_book_error(error)


@router.post(
    "/books/agent/discover",
    response_model=BookAgentResponse,
    summary="Use bounded Tool Calling to select verified public books",
)
async def agent_discover(request: BookAgentRequest) -> BookAgentResponse:
    try:
        return await BookAgent().discover(request)
    except BookServiceError as error:
        _raise_book_error(error)


@router.post(
    "/books/agent/discover/stream",
    summary="Stream safe progress events from the public-book Agent",
)
async def agent_discover_stream(request: BookAgentRequest) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

    async def emit(event: dict[str, object]) -> None:
        await queue.put(event)

    async def run_agent() -> None:
        try:
            await BookAgent().discover(request, on_event=emit)
        except BookServiceError as error:
            await queue.put(
                {"type": "error", "code": error.code, "message": error.public_message}
            )
        except Exception:
            logger.exception("Book Agent stream failed unexpectedly")
            await queue.put(
                {"type": "error", "message": "公开图书智能体暂时不可用，请稍后重试。"}
            )
        finally:
            await queue.put(None)

    agent_task = asyncio.create_task(run_agent())

    async def event_stream():
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                event_type = event.get("type", "message")
                yield (
                    f"event: {event_type}\n"
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                )
        finally:
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
