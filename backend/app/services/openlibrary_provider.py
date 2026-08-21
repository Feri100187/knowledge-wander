"""Open Library Search API provider."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.models.book import PublicBook
from app.services.book_errors import BookServiceError
from app.services.public_book_utils import (
    as_text,
    first_text,
    isbn_pair,
    publication_year,
    stable_book_id,
    text_list,
)

logger = logging.getLogger(__name__)

OPENLIBRARY_FIELDS = (
    "key,title,author_name,first_publish_year,publish_year,isbn,publisher,"
    "subject,language,cover_i,edition_key"
)


class OpenLibraryProvider:
    """Fetch normalized book metadata from Open Library without HTML scraping."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        base_url: str = "https://openlibrary.org",
        contact_email: str | None = None,
        timeout_seconds: float = 15.0,
        min_interval_seconds: float = 0.4,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None
        self.base_url = base_url.rstrip("/")
        self.contact_email = contact_email.strip() if contact_email else ""
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._throttle_lock = asyncio.Lock()
        self._last_request_at = 0.0

    @classmethod
    def from_env(cls) -> "OpenLibraryProvider":
        import os

        try:
            timeout = float(os.getenv("OPENLIBRARY_TIMEOUT_SECONDS", "15") or "15")
        except ValueError:
            timeout = 15.0
        return cls(
            base_url=os.getenv("OPENLIBRARY_BASE_URL", "https://openlibrary.org"),
            contact_email=os.getenv("OPENLIBRARY_CONTACT_EMAIL", ""),
            timeout_seconds=max(1.0, min(timeout, 60.0)),
        )

    @property
    def user_agent(self) -> str:
        return (
            f"KnowledgeWander/1.0 ({self.contact_email})"
            if self.contact_email
            else "KnowledgeWander/1.0"
        )

    async def search(
        self,
        query: str,
        *,
        page: int = 1,
        limit: int = 10,
        language: str | None = None,
    ) -> list[PublicBook]:
        normalized_query = query.strip()
        if not normalized_query:
            raise BookServiceError("INVALID_RESPONSE", message="请输入检索关键词。")

        await self._wait_for_throttle()
        params: dict[str, str | int] = {
            "q": normalized_query,
            "page": page,
            "limit": min(limit, 20),
            "fields": OPENLIBRARY_FIELDS,
        }
        if language and language.strip():
            params["lang"] = language.strip()

        started_at = time.perf_counter()
        try:
            response = await self._client.get(
                f"{self.base_url}/search.json",
                params=params,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise BookServiceError("SEARCH_TIMEOUT", reason="openlibrary_timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Open Library request failed status=%s", exc.response.status_code)
            raise BookServiceError("BOOK_SOURCE_UNAVAILABLE", reason="openlibrary_http_error") from exc
        except httpx.RequestError as exc:
            raise BookServiceError("BOOK_SOURCE_UNAVAILABLE", reason="openlibrary_request_error") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BookServiceError("INVALID_RESPONSE", reason="openlibrary_invalid_json") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("docs"), list):
            raise BookServiceError("INVALID_RESPONSE", reason="openlibrary_invalid_shape")

        books: list[PublicBook] = []
        for raw_doc in payload["docs"]:
            if not isinstance(raw_doc, dict):
                continue
            try:
                book = self.normalize_doc(raw_doc)
            except Exception:
                logger.info("Skipped malformed Open Library document")
                continue
            if book is not None:
                books.append(book)

        logger.info(
            "Open Library search completed query_length=%d result_count=%d latency_ms=%.2f",
            len(normalized_query),
            len(books),
            (time.perf_counter() - started_at) * 1000,
        )
        return books

    async def _wait_for_throttle(self) -> None:
        async with self._throttle_lock:
            now = time.monotonic()
            wait_seconds = self.min_interval_seconds - (now - self._last_request_at)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._last_request_at = time.monotonic()

    @classmethod
    def normalize_doc(cls, raw_doc: dict[str, Any]) -> PublicBook | None:
        title = as_text(raw_doc.get("title"))
        if not title:
            return None

        source_id = as_text(raw_doc.get("key")) or first_text(raw_doc.get("edition_key"))
        isbn10, isbn13 = isbn_pair(raw_doc.get("isbn"))
        source_id = source_id or isbn13 or isbn10
        if not source_id:
            return None

        year = publication_year(
            raw_doc.get("first_publish_year") or raw_doc.get("publish_year")
        )
        key = source_id if source_id.startswith("/") else f"/{source_id}"
        if key.startswith("/works/"):
            info_url = f"https://openlibrary.org{key}"
        elif key.startswith("/books/"):
            info_url = f"https://openlibrary.org{key}"
        else:
            info_url = None

        cover_id = raw_doc.get("cover_i")
        cover_url = (
            f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
            if isinstance(cover_id, int) or (isinstance(cover_id, str) and cover_id.isdigit())
            else None
        )
        authors = text_list(raw_doc.get("author_name"), limit=20)
        return PublicBook(
            id=stable_book_id("openlibrary", source_id, isbn10=isbn10, isbn13=isbn13),
            source="openlibrary",
            source_id=source_id,
            title=title,
            authors=authors,
            publisher=first_text(raw_doc.get("publisher")),
            published_date=year,
            publication_year=year,
            isbn_10=isbn10,
            isbn_13=isbn13,
            subjects=text_list(raw_doc.get("subject"), limit=30),
            description=None,
            language=_open_library_language(raw_doc.get("language")),
            cover_url=cover_url,
            info_url=info_url,
            preview_url=None,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _open_library_language(value: Any) -> str | None:
    raw = first_text(value)
    if not raw:
        return None
    return raw.rsplit("/", 1)[-1]
