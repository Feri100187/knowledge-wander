"""Unit and API tests for the public Open Library / Google Books pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import books as books_api
from app.main import app
from app.models.book import BookRecommendRequest, BookSearchResponse, PublicBook
from app.services.book_errors import BookServiceError
from app.services.google_books_provider import GoogleBooksProvider
from app.services.openlibrary_provider import OpenLibraryProvider
from app.services.public_book_service import PublicBookSearchService, PublicBookService


def run(awaitable: Any) -> Any:
    return asyncio.run(awaitable)


class FakeResponse:
    def __init__(self, payload: Any = None, *, json_error: bool = False) -> None:
        self.payload = payload
        self.json_error = json_error

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        if self.json_error:
            raise ValueError("invalid json")
        return self.payload


class FakeHttpClient:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response

    async def aclose(self) -> None:
        return None


def public_book(
    book_id: str,
    title: str,
    *,
    source: str = "openlibrary",
    isbn_13: str | None = None,
    description: str | None = None,
    authors: list[str] | None = None,
) -> PublicBook:
    return PublicBook(
        id=isbn_13 and f"isbn:{isbn_13}" or f"{source}:{book_id}",
        source=source,
        source_id=book_id,
        title=title,
        authors=authors or ["示例作者"],
        publisher="示例出版社" if description else None,
        published_date="2024",
        publication_year="2024",
        isbn_10=None,
        isbn_13=isbn_13,
        subjects=["主题"],
        description=description,
        language="chi",
        cover_url=None,
        info_url=None,
        preview_url=None,
    )


def open_library_doc(index: int = 1) -> dict[str, Any]:
    return {
        "key": f"/works/OL{index}W",
        "title": "程序化叙事设计",
        "author_name": ["示例作者"],
        "first_publish_year": 2024,
        "publish_year": [2024],
        "isbn": ["9780306406157", "0306406152"],
        "publisher": ["示例出版社"],
        "subject": ["叙事", "游戏设计"],
        "language": ["/languages/chi"],
        "cover_i": 12345,
        "edition_key": [f"OL{index}M"],
    }


def google_item(volume_id: str = "vol-1") -> dict[str, Any]:
    return {
        "id": volume_id,
        "volumeInfo": {
            "title": "公开图书设计",
            "authors": ["Google 作者"],
            "publisher": "Google 出版社",
            "publishedDate": "2023-05-01",
            "industryIdentifiers": [
                {"type": "ISBN_13", "identifier": "9781234567897"},
                {"type": "ISBN_10", "identifier": "1234567890"},
            ],
            "categories": ["设计"],
            "description": "来自公开 API 的简介。",
            "language": "zh",
            "imageLinks": {"thumbnail": "http://books.example/cover.jpg"},
            "infoLink": "https://books.google.com/books?id=vol-1",
            "previewLink": "https://books.google.com/books?id=vol-1&pg=PA1",
        },
    }


def test_open_library_normalizes_explicit_fields_and_safe_headers() -> None:
    client = FakeHttpClient(FakeResponse({"numFound": 1, "docs": [open_library_doc()]}))
    provider = OpenLibraryProvider(client=client, contact_email="contact@example.test")

    books = run(provider.search("程序化叙事", page=1, limit=10, language="chi"))

    assert len(books) == 1
    book = books[0]
    assert book.id == "isbn:9780306406157"
    assert book.source == "openlibrary"
    assert book.authors == ["示例作者"]
    assert book.isbn_10 == "0306406152"
    assert book.cover_url == "https://covers.openlibrary.org/b/id/12345-M.jpg"
    assert book.info_url == "https://openlibrary.org/works/OL1W"
    assert book.subjects == ["叙事", "游戏设计"]
    url, kwargs = client.calls[0]
    assert url.endswith("/search.json")
    assert kwargs["params"]["fields"] != "*"
    assert "key" in kwargs["params"]["fields"]
    assert kwargs["headers"]["User-Agent"] == "KnowledgeWander/1.0 (contact@example.test)"


def test_open_library_ignores_malformed_docs_and_supports_empty_results() -> None:
    client = FakeHttpClient(FakeResponse({"numFound": 2, "docs": [None, {"title": "没有稳定 ID"}]}))
    provider = OpenLibraryProvider(client=client, min_interval_seconds=0)

    assert run(provider.search("empty", page=1, limit=10, language=None)) == []


@pytest.mark.parametrize(
    ("response", "error_code"),
    [
        (FakeResponse(json_error=True), "INVALID_RESPONSE"),
        (None, "SEARCH_TIMEOUT"),
    ],
)
def test_open_library_maps_invalid_and_timeout(
    response: FakeResponse | None,
    error_code: str,
) -> None:
    error = httpx.ReadTimeout("timeout") if error_code == "SEARCH_TIMEOUT" else None
    provider = OpenLibraryProvider(
        client=FakeHttpClient(response=response, error=error),
        min_interval_seconds=0,
    )

    with pytest.raises(BookServiceError) as caught:
        run(provider.search("query", page=1, limit=10, language=None))
    assert caught.value.code == error_code


def test_google_books_normalizes_metadata_and_only_sends_configured_key() -> None:
    client = FakeHttpClient(FakeResponse({"totalItems": 1, "items": [google_item()]}))
    provider = GoogleBooksProvider(client=client, api_key="server-only-key")

    books = run(provider.search("公开图书", page=1, limit=10, language="zh"))

    assert len(books) == 1
    book = books[0]
    assert book.id == "isbn:9781234567897"
    assert book.description == "来自公开 API 的简介。"
    assert book.cover_url == "https://books.example/cover.jpg"
    assert book.preview_url == "https://books.google.com/books?id=vol-1&pg=PA1"
    assert book.isbn_10 == "1234567890"
    assert client.calls[0][1]["params"]["key"] == "server-only-key"
    assert client.calls[0][1]["params"]["langRestrict"] == "zh"


def test_google_books_omits_empty_key_and_maps_invalid_response() -> None:
    client = FakeHttpClient(FakeResponse({"items": "bad"}))
    provider = GoogleBooksProvider(client=client, api_key="")

    with pytest.raises(BookServiceError) as caught:
        run(provider.search("query", page=1, limit=10, language=None))
    assert caught.value.code == "INVALID_RESPONSE"
    assert "key" not in client.calls[0][1]["params"]


class FakeProvider:
    def __init__(self, results: list[PublicBook] | None = None, error: BookServiceError | None = None) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def search(self, query: str, **kwargs: Any) -> list[PublicBook]:
        self.calls.append({"query": query, **kwargs})
        if self.error:
            raise self.error
        return list(self.results)

    async def close(self) -> None:
        return None


def test_composite_skips_google_when_open_library_has_enough_results() -> None:
    open_library = FakeProvider([public_book(str(i), f"书{i}") for i in range(5)])
    google = FakeProvider([public_book("g", "Google 书", source="google_books")])
    service = PublicBookSearchService(open_library, google, cache_ttl_seconds=600, cache_max_entries=10)

    result = run(service.search_books("主题", page=1, limit=4, language=None))

    assert len(result.books) == 4
    assert len(open_library.calls) == 1
    assert google.calls == []


def test_composite_falls_back_and_deduplicates_by_isbn_and_cache() -> None:
    isbn = "9780306406157"
    primary = public_book("ol", "同一本书", isbn_13=isbn)
    fallback = public_book("google", "同一本书（完整元数据）", source="google_books", isbn_13=isbn, description="更完整简介")
    open_library = FakeProvider([primary])
    google = FakeProvider([fallback, public_book("g2", "另一本文献", source="google_books")])
    service = PublicBookSearchService(open_library, google, cache_ttl_seconds=600, cache_max_entries=10)

    first = run(service.search_books("主题", page=1, limit=10, language=None))
    second = run(service.search_books("主题", page=1, limit=10, language=None))

    assert len(first.books) == 2
    assert first.books[0].id == f"isbn:{isbn}"
    assert first.books[0].description == "更完整简介"
    assert [book.id for book in second.books] == [book.id for book in first.books]
    assert len(open_library.calls) == 1
    assert len(google.calls) == 1


def test_composite_degrades_when_one_source_fails_and_errors_when_both_fail() -> None:
    open_book = public_book("ol", "Open Library 结果")
    open_library = FakeProvider([open_book], error=None)
    google = FakeProvider(error=BookServiceError("BOOK_SOURCE_UNAVAILABLE"))
    service = PublicBookSearchService(open_library, google, cache_ttl_seconds=600, cache_max_entries=10)
    assert len(run(service.search_books("主题", page=1, limit=10, language=None)).books) == 1

    failed_open = FakeProvider(error=BookServiceError("SEARCH_TIMEOUT"))
    failed_google = FakeProvider(error=BookServiceError("BOOK_SOURCE_UNAVAILABLE"))
    unavailable = PublicBookSearchService(failed_open, failed_google, cache_ttl_seconds=600, cache_max_entries=10)
    with pytest.raises(BookServiceError) as caught:
        run(unavailable.search_books("主题", page=1, limit=10, language=None))
    assert caught.value.code == "BOOK_SOURCE_UNAVAILABLE"


def test_recommendation_uses_public_metadata_only() -> None:
    service = PublicBookService(
        PublicBookSearchService(
            FakeProvider([public_book("node", "程序化叙事设计", description="关于程序化叙事的简介")]),
            FakeProvider(),
            cache_ttl_seconds=600,
            cache_max_entries=10,
        )
    )
    response = run(service.recommend_books(BookRecommendRequest(
        root_topic="游戏开发",
        node_label="程序化叙事",
        node_domain="游戏设计",
        surprise_level=0.5,
    )))
    assert response.books[0].id.startswith("openlibrary:")
    assert response.books[0].reason
    assert "available" not in response.books[0].model_dump()


def test_books_api_routes_use_public_names_and_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = PublicBookService(
        PublicBookSearchService(
            FakeProvider([public_book("api", "API 书目")]),
            FakeProvider(),
            cache_ttl_seconds=600,
            cache_max_entries=10,
        )
    )
    monkeypatch.setattr(books_api, "get_book_service", lambda: fake_service)
    client = TestClient(app)

    response = client.get("/api/books/search", params={"q": "Python"})
    assert response.status_code == 200
    assert response.json()["books"][0]["source"] == "openlibrary"

    monkeypatch.setattr(
        books_api,
        "get_book_service",
        lambda: PublicBookService(
            PublicBookSearchService(
                FakeProvider(error=BookServiceError("BOOK_SOURCE_UNAVAILABLE")),
                FakeProvider(error=BookServiceError("BOOK_SOURCE_UNAVAILABLE")),
                cache_ttl_seconds=600,
                cache_max_entries=10,
            )
        ),
    )
    unavailable = client.get("/api/books/search", params={"q": "Python"})
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["code"] == "BOOK_SOURCE_UNAVAILABLE"
