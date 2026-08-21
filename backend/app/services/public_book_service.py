"""Composite public-book search and knowledge-node recommendation service."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

from app.models.book import (
    BookRecommendRequest,
    BookRecommendResponse,
    BookRecommendation,
    BookSearchResponse,
    PublicBook,
)
from app.services.book_errors import BookServiceError
from app.services.book_search_query import BookSearchQueryBuilder, BookSearchTerms
from app.services.google_books_provider import GoogleBooksProvider
from app.services.openlibrary_provider import OpenLibraryProvider
from app.services.public_book_utils import normalized_title_author

logger = logging.getLogger(__name__)

PUBLIC_BOOK_DATA_SOURCE = "public_api"
PUBLIC_BOOK_DATA_NOTICE = "书目元数据来自 Open Library 与 Google Books 公共 API。"
NO_BOOK_RECOMMENDATION_MESSAGE = "暂未找到与该知识节点相关的公开图书。"
OPEN_LIBRARY_FALLBACK_THRESHOLD = 5
ENGLISH_BOOK_QUERY_LANGUAGE = "en"


class BookProvider(Protocol):
    async def search(
        self,
        query: str,
        *,
        page: int,
        limit: int,
        language: str | None,
    ) -> list[PublicBook]: ...

    async def close(self) -> None: ...


@dataclass
class _CacheEntry:
    created_at: float
    response: BookSearchResponse


@dataclass
class _ProviderSearchOutcome:
    books: list[PublicBook]
    attempts: int
    failures: int


class PublicBookSearchService:
    """Use Open Library first and Google Books only when more coverage is needed."""

    def __init__(
        self,
        openlibrary: BookProvider | None = None,
        google_books: BookProvider | None = None,
        *,
        cache_ttl_seconds: float | None = None,
        cache_max_entries: int | None = None,
        query_builder: BookSearchQueryBuilder | None = None,
    ) -> None:
        self.openlibrary = openlibrary or OpenLibraryProvider.from_env()
        self.google_books = google_books or GoogleBooksProvider.from_env()
        self.query_builder = query_builder or BookSearchQueryBuilder()
        self.cache_ttl_seconds = max(
            1.0,
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else _env_float("BOOK_SEARCH_CACHE_TTL_SECONDS", 600.0),
        )
        self.cache_max_entries = max(
            1,
            cache_max_entries
            if cache_max_entries is not None
            else _env_int("BOOK_SEARCH_CACHE_MAX_ENTRIES", 200),
        )
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()

    async def search_books(
        self,
        query: str,
        *,
        page: int = 1,
        limit: int = 10,
        language: str | None = None,
    ) -> BookSearchResponse:
        response, _terms = await self.search_books_with_terms(
            query,
            page=page,
            limit=limit,
            language=language,
        )
        return response

    async def search_books_with_terms(
        self,
        query: str,
        *,
        page: int = 1,
        limit: int = 10,
        language: str | None = None,
    ) -> tuple[BookSearchResponse, BookSearchTerms]:
        normalized_query = query.strip()
        if not normalized_query:
            raise BookServiceError("INVALID_RESPONSE", message="请输入检索关键词。")
        if page < 1 or limit < 1 or limit > 20:
            raise BookServiceError("INVALID_RESPONSE", message="图书检索分页参数无效。")

        terms = await self.query_builder.build(normalized_query)
        primary_query = terms.primary_english_query
        if not primary_query:
            raise BookServiceError(
                "BOOK_QUERY_UNAVAILABLE",
                reason="english_query_unavailable",
            )

        key = self._cache_key(
            primary_query,
            terms.fallback_english_query,
            page,
            limit,
            language,
        )
        cached = self._get_cached(key)
        if cached is not None:
            logger.info(
                "Public book search cache hit english_query_length=%d",
                len(primary_query),
            )
            return cached.model_copy(update={"query": normalized_query}), terms

        search_queries = [primary_query]
        if (
            terms.fallback_english_query
            and terms.fallback_english_query.casefold() != primary_query.casefold()
        ):
            search_queries.append(terms.fallback_english_query)

        all_books: list[PublicBook] = []
        query_result_counts: dict[str, int] = {"primary": 0, "fallback": 0}
        attempts = 0
        failures = 0
        for query_index, search_query in enumerate(search_queries):
            outcome = await self._search_query_with_fallback(
                search_query,
                page=page,
                limit=limit,
                language=ENGLISH_BOOK_QUERY_LANGUAGE,
            )
            all_books.extend(outcome.books)
            attempts += outcome.attempts
            failures += outcome.failures
            query_result_counts["fallback" if query_index else "primary"] = len(outcome.books)

            merged_count = len(_merge_books([], all_books))
            if query_index == 0 and merged_count >= OPEN_LIBRARY_FALLBACK_THRESHOLD:
                break

        if not all_books and attempts > 0 and failures == attempts:
            raise BookServiceError(
                "BOOK_SOURCE_UNAVAILABLE",
                reason="all_book_sources_unavailable",
            )

        books = _rank_search_books(_merge_books([], all_books), terms)
        logger.info(
            "Public book english-only search completed original_query_length=%d "
            "primary_query_length=%d fallback_query_generated=%s primary_result_count=%d "
            "fallback_result_count=%d merged_count=%d",
            len(normalized_query),
            len(primary_query),
            bool(terms.fallback_english_query),
            query_result_counts["primary"],
            query_result_counts["fallback"],
            len(books),
        )
        response = BookSearchResponse(
            data_source=PUBLIC_BOOK_DATA_SOURCE,
            query=normalized_query,
            page=page,
            page_size=limit,
            total=len(books),
            books=books[:limit],
            error_code="NO_RESULTS" if not books else None,
            message="暂未找到匹配的公开图书。" if not books else None,
        )
        self._set_cached(key, response)
        return response.model_copy(deep=True), terms

    async def _search_query_with_fallback(
        self,
        query: str,
        *,
        page: int,
        limit: int,
        language: str | None,
    ) -> _ProviderSearchOutcome:
        openlibrary_books: list[PublicBook] = []
        google_books: list[PublicBook] = []
        attempts = 0
        failures = 0

        attempts += 1
        try:
            openlibrary_books = await self.openlibrary.search(
                query,
                page=page,
                limit=limit,
                language=language,
            )
        except BookServiceError as error:
            failures += 1
            logger.info(
                "Public book source failed source=openlibrary query_length=%d code=%s",
                len(query),
                error.code,
            )

        if len(openlibrary_books) < OPEN_LIBRARY_FALLBACK_THRESHOLD:
            attempts += 1
            try:
                google_books = await self.google_books.search(
                    query,
                    page=page,
                    limit=limit,
                    language=language,
                )
            except BookServiceError as error:
                failures += 1
                logger.info(
                    "Public book source failed source=google_books query_length=%d code=%s",
                    len(query),
                    error.code,
                )

        return _ProviderSearchOutcome(
            books=_merge_books(openlibrary_books, google_books),
            attempts=attempts,
            failures=failures,
        )

    def _cache_key(
        self,
        primary_query: str,
        fallback_query: str | None,
        page: int,
        limit: int,
        language: str | None,
    ) -> str:
        return "|".join(
            (
                primary_query.casefold(),
                (fallback_query or "").casefold(),
                str(page),
                str(limit),
                (language or "").strip().casefold(),
            )
        )

    def _get_cached(self, key: str) -> BookSearchResponse | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at >= self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry.response.model_copy(deep=True)

    def _set_cached(self, key: str, response: BookSearchResponse) -> None:
        self._cache[key] = _CacheEntry(time.monotonic(), response.model_copy(deep=True))
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_max_entries:
            self._cache.popitem(last=False)

    async def close(self) -> None:
        await self.openlibrary.close()
        await self.google_books.close()


class PublicBookService:
    """Application facade consumed by recommendation and Book Agent routes."""

    def __init__(self, search_service: PublicBookSearchService | None = None) -> None:
        self.search_service = search_service or PublicBookSearchService()

    async def search_books(
        self,
        query: str,
        *,
        page: int = 1,
        limit: int = 10,
        language: str | None = None,
    ) -> BookSearchResponse:
        return await self.search_service.search_books(
            query,
            page=page,
            limit=limit,
            language=language,
        )

    async def recommend_books(self, request: BookRecommendRequest) -> BookRecommendResponse:
        queries = _recommendation_queries(request)
        last_query = queries[-1]
        search_result: BookSearchResponse | None = None
        search_terms: BookSearchTerms | None = None
        query_error: BookServiceError | None = None
        for query in queries:
            last_query = query
            try:
                search_result, search_terms = await self.search_service.search_books_with_terms(
                    query,
                    page=1,
                    limit=20,
                    language=request.language,
                )
            except BookServiceError as error:
                if error.code != "BOOK_QUERY_UNAVAILABLE":
                    raise
                query_error = error
                continue
            if search_result.books:
                break

        if search_result is None or not search_result.books:
            if search_result is None and query_error is not None:
                return BookRecommendResponse(
                    data_source=PUBLIC_BOOK_DATA_SOURCE,
                    data_notice=PUBLIC_BOOK_DATA_NOTICE,
                    query=last_query,
                    books=[],
                    error_code=query_error.code,
                    message=query_error.public_message,
                )
            return BookRecommendResponse(
                data_source=PUBLIC_BOOK_DATA_SOURCE,
                data_notice=PUBLIC_BOOK_DATA_NOTICE,
                query=last_query,
                books=[],
                error_code="NO_RESULTS",
                message=NO_BOOK_RECOMMENDATION_MESSAGE,
            )

        ranked = []
        for book in search_result.books:
            relevance, match_text, match_source = _match_book(book, request, search_terms)
            completeness = _metadata_completeness(book)
            reason = _recommendation_reason(book, request, search_result.query, match_text, match_source)
            ranked.append((relevance, completeness, _year_value(book), book.title.casefold(), book, reason))

        ranked.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
        recommendations = [
            BookRecommendation(
                **book.model_dump(),
                reason=reason,
                relevance_score=round(relevance, 2),
            )
            for relevance, _completeness, _year, _title, book, reason in ranked[:6]
        ]
        return BookRecommendResponse(
            data_source=PUBLIC_BOOK_DATA_SOURCE,
            data_notice=PUBLIC_BOOK_DATA_NOTICE,
            query=search_result.query,
            books=recommendations,
        )

    async def close(self) -> None:
        await self.search_service.close()


def _recommendation_queries(request: BookRecommendRequest) -> list[str]:
    queries: list[str] = []
    for value in (request.node_label, request.node_domain, request.root_topic):
        normalized = value.strip()
        if normalized and normalized.casefold() not in {item.casefold() for item in queries}:
            queries.append(normalized)
    return queries


def _match_book(
    book: PublicBook,
    request: BookRecommendRequest,
    search_terms: BookSearchTerms | None = None,
) -> tuple[float, str | None, str | None]:
    candidates = (
        (request.node_label.strip(), 1.0),
        (request.node_domain.strip(), 0.9),
        (request.root_topic.strip(), 0.8),
    )
    searchable_subjects = " ".join(book.subjects)
    searchable_description = book.description or ""
    searchable_authors = " ".join(book.authors)

    if search_terms:
        display_query = next(
            (
                query
                for query in (
                    request.node_label,
                    request.node_domain,
                    request.root_topic,
                )
                if query.strip().casefold() == search_terms.original_query.casefold()
            ),
            request.node_label,
        )
        retrieval_queries = [
            query
            for query in (
                search_terms.primary_english_query,
                search_terms.fallback_english_query,
            )
            if query
        ]
        for retrieval_query in retrieval_queries:
            if _contains(book.title, retrieval_query):
                return 1.0, display_query, "title"
            if _contains(searchable_subjects, retrieval_query):
                return 0.85, display_query, "subject"
            if _contains(searchable_description, retrieval_query):
                return 0.75, display_query, "description"
            if _contains(searchable_authors, retrieval_query):
                return 0.6, display_query, "author"

    for query, weight in candidates:
        if _contains(book.title, query):
            return weight, query, "title"
    for query, weight in candidates:
        if _contains(searchable_subjects, query):
            return round(weight * 0.85, 4), query, "subject"
    for query, weight in candidates:
        if _contains(searchable_description, query):
            return round(weight * 0.75, 4), query, "description"
    for query, weight in candidates:
        if _contains(searchable_authors, query):
            return round(weight * 0.6, 4), query, "author"

    return 0.35, None, None


def _contains(value: str, query: str) -> bool:
    return bool(value and query and query.casefold() in value.casefold())


def _metadata_completeness(book: PublicBook) -> int:
    return sum(
        bool(value)
        for value in (
            book.authors,
            book.publisher,
            book.publication_year,
            book.isbn_13 or book.isbn_10,
            book.subjects,
            book.description,
            book.cover_url,
            book.info_url,
        )
    )


def _year_value(book: PublicBook) -> int:
    match = re.search(r"(\d{4})", book.publication_year or "")
    return int(match.group(1)) if match else 0


def _recommendation_reason(
    book: PublicBook,
    request: BookRecommendRequest,
    query: str,
    match_text: str | None,
    match_source: str | None,
) -> str:
    if match_source == "title" and match_text:
        reason = f"书名直接涉及“{match_text}”，与你当前探索到的“{request.node_label}”节点高度相关。"
    elif match_source == "subject" and match_text:
        reason = f"主题标签包含“{match_text}”，为“{request.node_label}”提供了相邻的阅读入口。"
    elif match_source == "description" and match_text:
        reason = f"公开书目简介提到“{match_text}”，与当前知识路径形成了可追踪的连接。"
    elif match_source == "author" and match_text:
        reason = f"作者信息与“{match_text}”相关，为当前主题提供了另一条探索路径。"
    else:
        reason = f"它来自公开图书数据库对“{query}”的检索结果，可作为当前节点的延伸阅读。"
    if book.subjects:
        reason += f" 主题标签包括“{book.subjects[0]}”。"
    return reason


def _merge_books(primary: list[PublicBook], fallback: list[PublicBook]) -> list[PublicBook]:
    merged: OrderedDict[str, PublicBook] = OrderedDict()
    keys: dict[str, str] = {}
    for book in [*primary, *fallback]:
        key = _dedupe_key(book)
        existing_key = keys.get(key)
        if existing_key is None:
            keys[key] = key
            merged[key] = book
            continue
        existing = merged[existing_key]
        if _metadata_completeness(book) > _metadata_completeness(existing):
            merged[existing_key] = book
    return list(merged.values())


def _rank_search_books(books: list[PublicBook], terms: BookSearchTerms) -> list[PublicBook]:
    ranked = list(enumerate(books))
    ranked.sort(
        key=lambda item: (
            -_book_search_relevance(item[1], terms),
            -_metadata_completeness(item[1]),
            -_year_value(item[1]),
            item[1].title.casefold(),
            item[0],
        )
    )
    return [book for _index, book in ranked]


def _book_search_relevance(book: PublicBook, terms: BookSearchTerms) -> float:
    queries = [
        query
        for query in (
            terms.primary_english_query,
            terms.fallback_english_query,
        )
        if query
    ]
    if not queries:
        return 0.0
    relevance = max(_query_match_score(book, query) for query in queries)

    language = (book.language or "").casefold()
    if language in {"en", "eng", "english"}:
        relevance += 0.03

    year = _year_value(book)
    if year:
        relevance += min(max(year - 1900, 0) / 200, 1) * 0.02
    return relevance


def _query_match_score(book: PublicBook, query: str) -> float:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return 0.0

    title = _normalize_search_text(book.title)
    subjects = _normalize_search_text(" ".join(book.subjects))
    description = _normalize_search_text(book.description or "")
    authors = _normalize_search_text(" ".join(book.authors))
    if normalized_query in title:
        return 1.0

    tokens = normalized_query.split()
    title_coverage = _token_coverage(tokens, title)
    subject_coverage = _token_coverage(tokens, subjects)
    description_coverage = _token_coverage(tokens, description)
    author_coverage = _token_coverage(tokens, authors)
    return max(
        0.86 * title_coverage,
        0.72 * subject_coverage,
        0.58 * description_coverage,
        0.42 * author_coverage,
    )


def _token_coverage(tokens: list[str], value: str) -> float:
    if not tokens or not value:
        return 0.0
    return sum(token in value for token in tokens) / len(tokens)


def _normalize_search_text(value: str) -> str:
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _dedupe_key(book: PublicBook) -> str:
    if book.isbn_13:
        return f"isbn13:{book.isbn_13}"
    if book.isbn_10:
        return f"isbn10:{book.isbn_10}"
    return f"title-author:{normalized_title_author(book.title, book.authors)}"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


_book_service = PublicBookService()


def get_book_service() -> PublicBookService:
    return _book_service


async def recommend_public_books(request: BookRecommendRequest) -> BookRecommendResponse:
    return await get_book_service().recommend_books(request)
