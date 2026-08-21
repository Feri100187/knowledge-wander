"""Safe, source-agnostic errors for public book APIs."""

from __future__ import annotations


ERROR_HTTP_STATUS: dict[str, int] = {
    "BOOK_SOURCE_UNAVAILABLE": 503,
    "BOOK_QUERY_UNAVAILABLE": 503,
    "SEARCH_TIMEOUT": 504,
    "INVALID_RESPONSE": 502,
}

ERROR_MESSAGE: dict[str, str] = {
    "BOOK_SOURCE_UNAVAILABLE": "公开图书数据源暂时不可用，请稍后重试。",
    "BOOK_QUERY_UNAVAILABLE": "暂时无法生成公开图书检索词，请稍后重试。",
    "SEARCH_TIMEOUT": "公开图书检索超时，请稍后重试。",
    "INVALID_RESPONSE": "公开图书数据源返回的数据格式无法识别。",
    "NO_RESULTS": "暂未找到匹配的公开图书。",
}


class BookServiceError(RuntimeError):
    """An error that can be safely exposed without raw provider payloads."""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.code = code
        self.reason = reason or code.casefold()
        self.public_message = message or ERROR_MESSAGE.get(
            code,
            ERROR_MESSAGE["BOOK_SOURCE_UNAVAILABLE"],
        )
        super().__init__(self.public_message)

    @property
    def http_status(self) -> int:
        return ERROR_HTTP_STATUS.get(self.code, 503)
