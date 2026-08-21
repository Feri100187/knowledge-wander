"""Small normalization helpers shared by public-book providers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def first_text(value: Any) -> str | None:
    if isinstance(value, str):
        return as_text(value)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        for item in value:
            text = as_text(item)
            if text:
                return text
    return None


def text_list(value: Any, *, limit: int = 30) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        return []
    result: list[str] = []
    for item in values:
        text = as_text(item)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_isbn(value: Any) -> str | None:
    text = as_text(value)
    if not text:
        return None
    compact = re.sub(r"[^0-9Xx]", "", text).upper()
    if len(compact) in {10, 13} and (compact[:-1].isdigit() or compact.isdigit()):
        return compact
    return None


def isbn_pair(values: Any) -> tuple[str | None, str | None]:
    candidates = values if isinstance(values, list) else [values]
    isbn10: str | None = None
    isbn13: str | None = None
    for value in candidates:
        normalized = normalize_isbn(value)
        if normalized is None:
            continue
        if len(normalized) == 13 and isbn13 is None:
            isbn13 = normalized
        elif len(normalized) == 10 and isbn10 is None:
            isbn10 = normalized
    return isbn10, isbn13


def publication_year(value: Any) -> str | None:
    if isinstance(value, list):
        values = value
    else:
        values = [value]
    years: list[int] = []
    for item in values:
        text = as_text(item)
        if not text:
            continue
        match = re.search(r"(\d{4})", text)
        if match:
            year = int(match.group(1))
            if 1000 <= year <= 3000:
                years.append(year)
    return str(max(years)) if years else None


def stable_book_id(
    source: str,
    source_id: str,
    *,
    isbn10: str | None,
    isbn13: str | None,
) -> str:
    if isbn13:
        return f"isbn:{isbn13}"
    if isbn10:
        return f"isbn:{isbn10}"
    return f"{source}:{source_id.strip().lstrip('/')}"


def normalized_title_author(title: str, authors: list[str]) -> str:
    author = authors[0] if authors else ""
    compact = re.sub(r"\s+", " ", f"{title} {author}".casefold()).strip()
    return compact
