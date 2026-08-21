"""Google Books Volumes API provider."""

from __future__ import annotations

import logging
import os
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


class GoogleBooksProvider:
    """Fetch normalized bibliographic metadata from Google Books."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        base_url: str = "https://www.googleapis.com/books/v1",
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip() if api_key else ""

    @classmethod
    def from_env(cls) -> "GoogleBooksProvider":
        try:
            timeout = float(os.getenv("GOOGLE_BOOKS_TIMEOUT_SECONDS", "15") or "15")
        except ValueError:
            timeout = 15.0
        return cls(
            base_url=os.getenv("GOOGLE_BOOKS_BASE_URL", "https://www.googleapis.com/books/v1"),
            api_key=os.getenv("GOOGLE_BOOKS_API_KEY", ""),
            timeout_seconds=max(1.0, min(timeout, 60.0)),
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

        params: dict[str, str | int] = {
            "q": normalized_query,
            "startIndex": max(page - 1, 0) * min(limit, 20),
            "maxResults": min(limit, 20),
            "orderBy": "relevance",
            "printType": "books",
        }
        if language and language.strip():
            params["langRestrict"] = language.strip()
        if self.api_key:
            params["key"] = self.api_key

        try:
            response = await self._client.get(
                f"{self.base_url}/volumes",
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise BookServiceError("SEARCH_TIMEOUT", reason="google_books_timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Google Books request failed status=%s", exc.response.status_code)
            raise BookServiceError("BOOK_SOURCE_UNAVAILABLE", reason="google_books_http_error") from exc
        except httpx.RequestError as exc:
            raise BookServiceError("BOOK_SOURCE_UNAVAILABLE", reason="google_books_request_error") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BookServiceError("INVALID_RESPONSE", reason="google_books_invalid_json") from exc

        if not isinstance(payload, dict):
            raise BookServiceError("INVALID_RESPONSE", reason="google_books_invalid_shape")
        raw_items = payload.get("items", [])
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raise BookServiceError("INVALID_RESPONSE", reason="google_books_items_invalid")

        books: list[PublicBook] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            try:
                book = self.normalize_item(raw_item)
            except Exception:
                logger.info("Skipped malformed Google Books item")
                continue
            if book is not None:
                books.append(book)
        return books

    @classmethod
    def normalize_item(cls, raw_item: dict[str, Any]) -> PublicBook | None:
        source_id = as_text(raw_item.get("id"))
        volume_info = raw_item.get("volumeInfo")
        if not source_id or not isinstance(volume_info, dict):
            return None
        title = as_text(volume_info.get("title"))
        if not title:
            return None

        isbn10, isbn13 = _google_isbn_pair(volume_info.get("industryIdentifiers"))
        published_date = as_text(volume_info.get("publishedDate"))
        image_links = volume_info.get("imageLinks")
        cover_url = None
        if isinstance(image_links, dict):
            cover_url = first_text(
                image_links.get("thumbnail") or image_links.get("smallThumbnail")
            )
            if cover_url and cover_url.startswith("http://"):
                cover_url = "https://" + cover_url[7:]

        return PublicBook(
            id=stable_book_id("google_books", source_id, isbn10=isbn10, isbn13=isbn13),
            source="google_books",
            source_id=source_id,
            title=title,
            authors=text_list(volume_info.get("authors"), limit=20),
            publisher=as_text(volume_info.get("publisher")),
            published_date=published_date,
            publication_year=publication_year(published_date),
            isbn_10=isbn10,
            isbn_13=isbn13,
            subjects=text_list(volume_info.get("categories"), limit=30),
            description=as_text(volume_info.get("description")),
            language=as_text(volume_info.get("language")),
            cover_url=cover_url,
            info_url=as_text(volume_info.get("infoLink")),
            preview_url=as_text(volume_info.get("previewLink")),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _google_isbn_pair(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, list):
        return None, None
    isbn10: str | None = None
    isbn13: str | None = None
    for identifier in value:
        if not isinstance(identifier, dict):
            continue
        identifier_type = as_text(identifier.get("type"))
        identifier_value = identifier.get("identifier")
        candidate10, candidate13 = isbn_pair(identifier_value)
        if identifier_type == "ISBN_10" and candidate10:
            isbn10 = isbn10 or candidate10
        elif identifier_type == "ISBN_13" and candidate13:
            isbn13 = isbn13 or candidate13
        else:
            isbn10 = isbn10 or candidate10
            isbn13 = isbn13 or candidate13
    return isbn10, isbn13
