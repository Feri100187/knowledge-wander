"""Build safe English-only query terms for public-book retrieval."""

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

把用户提供的知识概念转换成适合 Open Library 和 Google Books 的简短、标准英文书目检索词。
只返回一行 primary 英文检索词；如果确实有必要提高召回率，再返回第二行 fallback 英文检索词。
不要解释，不要完整句子，不要加引号、编号或 Markdown。
每行通常为 1 到 6 个英文单词，优先使用宽泛但准确的学术或书目领域标准术语。
不要改变原概念含义，不要把检索词写得过窄，也不要添加 books、book about、how to 等泛化词。
第二行只能是与第一行语义不同但仍相关的英文检索词，不要重复第一行。
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
    """Original user-facing term plus retrieval-only English terms."""

    original_query: str
    primary_english_query: str | None = None
    fallback_english_query: str | None = None

    @property
    def english_query(self) -> str | None:
        """Backward-compatible alias for the primary retrieval term."""

        return self.primary_english_query

    @property
    def english_fallback_query(self) -> str | None:
        """Backward-compatible alias for the optional fallback term."""

        return self.fallback_english_query


@dataclass
class _TranslationCacheEntry:
    created_at: float
    primary_english_query: str
    fallback_english_query: str | None


class BookSearchQueryBuilder:
    """Generate and cache compact English retrieval terms without changing app context."""

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
            english_query = _normalize_english_term(original_query)
            return BookSearchTerms(
                original_query=original_query,
                primary_english_query=english_query,
            )

        cache_key = original_query.casefold()
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info(
                "book search english_only=true original_query_length=%d "
                "english_query_generated=true cache_hit=true",
                len(original_query),
            )
            return BookSearchTerms(
                original_query=original_query,
                primary_english_query=cached.primary_english_query,
                fallback_english_query=cached.fallback_english_query,
            )

        llm = self._llm_service if self._llm_service is not None else get_llm_service()
        if llm is None:
            logger.info(
                "book search english_only=true original_query_length=%d "
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
                # StepFun may place its reasoning in a separate field; leave
                # enough completion budget for the visible final terms.
                max_tokens=512,
            )
            primary_english_query, fallback_english_query = _extract_english_terms(response)
        except Exception as exc:
            logger.warning(
                "english_query_generation_failed error=%s",
                type(exc).__name__,
            )
            return BookSearchTerms(original_query=original_query)

        if primary_english_query is None:
            logger.warning("english_query_generation_failed reason=invalid_term")
            return BookSearchTerms(original_query=original_query)

        self._set_cached(cache_key, primary_english_query, fallback_english_query)
        logger.info(
            "book search english_only=true original_query_length=%d "
            "english_query_generated=true cache_hit=false",
            len(original_query),
        )
        return BookSearchTerms(
            original_query=original_query,
            primary_english_query=primary_english_query,
            fallback_english_query=fallback_english_query,
        )

    def _get_cached(self, key: str) -> _TranslationCacheEntry | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at >= self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry

    def _set_cached(
        self,
        key: str,
        primary_english_query: str,
        fallback_english_query: str | None,
    ) -> None:
        self._cache[key] = _TranslationCacheEntry(
            time.monotonic(),
            primary_english_query,
            fallback_english_query,
        )
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_max_entries:
            self._cache.popitem(last=False)


def _contains_cjk(value: str) -> bool:
    return bool(_CJK_RE.search(value))


def _extract_english_terms(response: dict[str, Any]) -> tuple[str | None, str | None]:
    if not isinstance(response, dict):
        return None, None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None, None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None, None
    content = message.get("content")
    if not isinstance(content, str):
        return None, None

    candidate = content.strip()
    code_block = re.fullmatch(r"```(?:text|plain)?\s*(.*?)\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if code_block:
        candidate = code_block.group(1).strip()

    candidates = [line.strip() for line in candidate.splitlines() if line.strip()]
    if not candidates:
        return None, None
    terms: list[str] = []
    for raw_candidate in candidates[:2]:
        normalized = _normalize_english_term(raw_candidate)
        if normalized is None:
            continue
        if normalized in terms:
            continue
        terms.append(normalized)
    if not terms:
        return None, None
    return terms[0], terms[1] if len(terms) > 1 else None


def _normalize_english_term(candidate: str) -> str | None:
    candidate = re.sub(
        r"^(?:primary(?:_english)?|fallback(?:_english)?|alternate)\s*:\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", candidate)
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
