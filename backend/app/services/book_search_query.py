"""Build safe bilingual query terms for public-book retrieval."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

BOOK_SEARCH_TERM_SYSTEM_PROMPT = """你是公开图书检索关键词生成器。

把用户提供的中文知识概念转换成一个简短、标准、适合 Open Library 和 Google Books 的英文书目检索词。
只返回一个英文检索词组，不要解释，不要完整句子，不要加引号或 Markdown。
检索词通常为 1 到 6 个英文单词，优先使用学术或书目领域中的标准术语。
不要改变原概念含义，也不要添加 books、book about、how to 等泛化词。
"""

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ENGLISH_TERM_RE = re.compile(
    r"[A-Za-z][A-Za-z'/-]*(?:\s+[A-Za-z][A-Za-z'/-]*){0,5}"
)


class BookSearchTermLLM(Protocol):
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class BookSearchTerms:
    """Original user-facing term plus optional retrieval-only English term."""

    original_query: str
    english_query: str | None = None


@dataclass
class _TranslationCacheEntry:
    created_at: float
    english_query: str


class BookSearchQueryBuilder:
    """Generate and cache one compact English term without changing app context."""

    def __init__(
        self,
        llm_service: BookSearchTermLLM | None = None,
        *,
        cache_ttl_seconds: float | None = None,
        cache_max_entries: int | None = None,
    ) -> None:
        self._llm_service = llm_service
        self.cache_ttl_seconds = max(
            60.0,
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else _env_float("BOOK_SEARCH_ENGLISH_CACHE_TTL_SECONDS", 2700.0),
        )
        self.cache_max_entries = max(
            1,
            cache_max_entries
            if cache_max_entries is not None
            else _env_int("BOOK_SEARCH_ENGLISH_CACHE_MAX_ENTRIES", 200),
        )
        self._cache: OrderedDict[str, _TranslationCacheEntry] = OrderedDict()

    async def build(self, query: str) -> BookSearchTerms:
        original_query = query.strip()
        if not _contains_cjk(original_query):
            return BookSearchTerms(original_query=original_query)

        cache_key = original_query.casefold()
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info(
                "book search bilingual=true original_query_length=%d "
                "english_query_generated=true cache_hit=true",
                len(original_query),
            )
            return BookSearchTerms(original_query=original_query, english_query=cached)

        llm = self._llm_service if self._llm_service is not None else get_llm_service()
        if llm is None:
            logger.info(
                "book search bilingual=true original_query_length=%d "
                "english_query_generated=false reason=llm_unavailable",
                len(original_query),
            )
            return BookSearchTerms(original_query=original_query)

        try:
            response = await llm.chat_completion(
                [
                    {"role": "system", "content": BOOK_SEARCH_TERM_SYSTEM_PROMPT},
                    {"role": "user", "content": original_query},
                ],
                temperature=0.0,
                max_tokens=96,
            )
            english_query = _extract_english_term(response)
        except Exception as exc:
            logger.warning(
                "english_query_generation_failed error=%s",
                type(exc).__name__,
            )
            return BookSearchTerms(original_query=original_query)

        if english_query is None:
            logger.warning("english_query_generation_failed reason=invalid_term")
            return BookSearchTerms(original_query=original_query)

        self._set_cached(cache_key, english_query)
        logger.info(
            "book search bilingual=true original_query_length=%d "
            "english_query_generated=true cache_hit=false",
            len(original_query),
        )
        return BookSearchTerms(original_query=original_query, english_query=english_query)

    def _get_cached(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at >= self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry.english_query

    def _set_cached(self, key: str, english_query: str) -> None:
        self._cache[key] = _TranslationCacheEntry(time.monotonic(), english_query)
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_max_entries:
            self._cache.popitem(last=False)


def _contains_cjk(value: str) -> bool:
    return bool(_CJK_RE.search(value))


def _extract_english_term(response: dict[str, Any]) -> str | None:
    if not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None

    candidate = content.strip()
    code_block = re.fullmatch(r"```(?:text|plain)?\s*(.*?)\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if code_block:
        candidate = code_block.group(1).strip()
    if "\n" in candidate:
        candidate = candidate.splitlines()[0].strip()
    candidate = candidate.strip("`\"' ")
    if not _ENGLISH_TERM_RE.fullmatch(candidate):
        return None
    normalized = " ".join(candidate.casefold().split())
    if any(word in {"book", "books", "about", "how", "read"} for word in normalized.split()):
        return None
    return normalized


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
