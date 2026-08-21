import type {
  BookAgentBook,
  BookAgentRequest,
  BookAgentResponse,
  BookAgentStreamEvent,
  BookAgentStreamMetrics,
  BookAgentToolTrace,
  BookRecommendRequest,
  BookRecommendResponse,
  BookSearchRequest,
  BookSearchResponse,
  PublicBook,
} from "@/types/book";
import { buildApiUrl } from "@/lib/apiBaseUrl";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isPublicBook(value: unknown): value is PublicBook {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    (value.source === "openlibrary" || value.source === "google_books") &&
    typeof value.source_id === "string" &&
    typeof value.title === "string" &&
    isStringArray(value.authors) &&
    isNullableString(value.publisher) &&
    isNullableString(value.published_date) &&
    isNullableString(value.publication_year) &&
    isNullableString(value.isbn_10) &&
    isNullableString(value.isbn_13) &&
    isStringArray(value.subjects) &&
    isNullableString(value.description) &&
    isNullableString(value.language) &&
    isNullableString(value.cover_url) &&
    isNullableString(value.info_url) &&
    isNullableString(value.preview_url)
  );
}

function isBookRecommendation(value: unknown): boolean {
  return (
    isPublicBook(value) &&
    isRecord(value) &&
    typeof value.reason === "string" &&
    typeof value.relevance_score === "number"
  );
}

function isBookSearchResponse(value: unknown): value is BookSearchResponse {
  return (
    isRecord(value) &&
    typeof value.data_source === "string" &&
    typeof value.query === "string" &&
    typeof value.page === "number" &&
    typeof value.page_size === "number" &&
    typeof value.total === "number" &&
    Array.isArray(value.books) &&
    value.books.every(isPublicBook) &&
    isNullableString(value.error_code) &&
    isNullableString(value.message)
  );
}

function isBookRecommendResponse(value: unknown): value is BookRecommendResponse {
  return (
    isRecord(value) &&
    typeof value.data_source === "string" &&
    typeof value.data_notice === "string" &&
    typeof value.query === "string" &&
    Array.isArray(value.books) &&
    value.books.every(isBookRecommendation) &&
    isNullableString(value.error_code) &&
    isNullableString(value.message)
  );
}

function isBookAgentBook(value: unknown): value is BookAgentBook {
  return isRecord(value) && isPublicBook(value.book) && typeof value.reason === "string";
}

function isBookAgentToolTrace(value: unknown): value is BookAgentToolTrace {
  return (
    isRecord(value) &&
    value.tool === "search_books" &&
    typeof value.query === "string" &&
    isNullableString(value.language) &&
    typeof value.result_count === "number" &&
    (value.duration_ms === null || typeof value.duration_ms === "number")
  );
}

function isBookAgentResponse(value: unknown): value is BookAgentResponse {
  return (
    isRecord(value) &&
    (value.mode === "agent" || value.mode === "fallback") &&
    typeof value.tool_used === "boolean" &&
    typeof value.summary === "string" &&
    isStringArray(value.queries) &&
    Array.isArray(value.books) &&
    value.books.every(isBookAgentBook) &&
    Array.isArray(value.tool_trace) &&
    value.tool_trace.every(isBookAgentToolTrace) &&
    typeof value.tool_calls === "number" &&
    typeof value.tool_latency_ms === "number" &&
    typeof value.llm_rounds === "number" &&
    typeof value.agent_total_latency_ms === "number" &&
    typeof value.fallback_used === "boolean"
  );
}

function isBookAgentStreamMetrics(value: unknown): value is BookAgentStreamMetrics {
  return (
    isRecord(value) &&
    (value.mode === "agent" || value.mode === "fallback") &&
    typeof value.tool_used === "boolean" &&
    isStringArray(value.queries) &&
    Array.isArray(value.tool_trace) &&
    value.tool_trace.every(isBookAgentToolTrace) &&
    typeof value.tool_calls === "number" &&
    typeof value.tool_latency_ms === "number" &&
    typeof value.llm_rounds === "number" &&
    typeof value.agent_total_latency_ms === "number" &&
    typeof value.fallback_used === "boolean"
  );
}

export function isBookAgentStreamEvent(value: unknown): value is BookAgentStreamEvent {
  if (!isRecord(value) || typeof value.type !== "string") {
    return false;
  }
  if (value.type === "agent_started") {
    return true;
  }
  if (value.type === "path") {
    return isStringArray(value.path);
  }
  if (value.type === "tool_call") {
    return value.tool === "search_books" && typeof value.query === "string";
  }
  if (value.type === "tool_result") {
    return (
      typeof value.query === "string" &&
      typeof value.result_count === "number" &&
      (value.duration_ms === null || typeof value.duration_ms === "number")
    );
  }
  if (value.type === "final_selection") {
    return typeof value.book_count === "number";
  }
  if (value.type === "book") {
    return isPublicBook(value.book) && typeof value.reason === "string";
  }
  if (value.type === "complete") {
    return typeof value.summary === "string" && isBookAgentStreamMetrics(value.metrics);
  }
  if (value.type === "error") {
    return (
      typeof value.message === "string" &&
      (value.code === undefined || typeof value.code === "string")
    );
  }
  return false;
}

export class BookApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "BookApiError";
    this.code = code;
  }
}

async function throwApiError(response: Response): Promise<never> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // Keep a stable user-facing error even when the server response is not JSON.
  }
  const detail = isRecord(payload) && isRecord(payload.detail) ? payload.detail : null;
  const code = detail && typeof detail.code === "string" ? detail.code : "BOOK_SOURCE_UNAVAILABLE";
  const message = detail && typeof detail.message === "string"
    ? detail.message
    : "暂时无法连接公开图书数据源。";
  throw new BookApiError(code, message);
}

export async function requestBookRecommendation(
  request: BookRecommendRequest,
): Promise<BookRecommendResponse> {
  const response = await fetch(buildApiUrl("/api/books/recommend"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    return throwApiError(response);
  }
  const payload: unknown = await response.json();
  if (!isBookRecommendResponse(payload)) {
    throw new BookApiError("INVALID_RESPONSE", "公开图书推荐响应格式异常。");
  }
  return payload;
}

export async function requestBookAgent(
  request: BookAgentRequest,
): Promise<BookAgentResponse> {
  const response = await fetch(buildApiUrl("/api/books/agent/discover"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    return throwApiError(response);
  }
  const payload: unknown = await response.json();
  if (!isBookAgentResponse(payload)) {
    throw new BookApiError("INVALID_RESPONSE", "公开图书智能体响应格式异常。");
  }
  return payload;
}

function parseSseBlock(block: string): BookAgentStreamEvent | null {
  let data = "";
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("data:")) {
      data += line.slice(5).trimStart();
    }
  }
  if (!data) {
    return null;
  }
  try {
    const payload: unknown = JSON.parse(data);
    return isBookAgentStreamEvent(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function requestBookAgentStream(
  request: BookAgentRequest,
  onEvent: (event: BookAgentStreamEvent) => void,
): Promise<void> {
  const response = await fetch(buildApiUrl("/api/books/agent/discover/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    return throwApiError(response);
  }
  if (!response.body) {
    throw new BookApiError("INVALID_RESPONSE", "公开图书智能体没有返回进度流。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawTerminalEvent = false;

  const deliverEvent = (event: BookAgentStreamEvent) => {
    if (event.type === "complete" || event.type === "error") {
      sawTerminalEvent = true;
    }
    onEvent(event);
  };
  const consumeBlocks = () => {
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (event) {
        deliverEvent(event);
      }
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      if (buffer.trim()) {
        const event = parseSseBlock(buffer);
        if (event) {
          deliverEvent(event);
        }
      }
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    consumeBlocks();
  }

  if (!sawTerminalEvent) {
    throw new BookApiError("INCOMPLETE_STREAM", "公开图书智能体进度流中断，请重试。");
  }
}

export async function searchBooks(request: BookSearchRequest): Promise<BookSearchResponse> {
  const params = new URLSearchParams({
    q: request.q,
    limit: String(request.limit ?? 10),
    page: String(request.page ?? 1),
  });
  if (request.language) {
    params.set("language", request.language);
  }
  const response = await fetch(buildApiUrl(`/api/books/search?${params.toString()}`), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return throwApiError(response);
  }
  const payload: unknown = await response.json();
  if (!isBookSearchResponse(payload)) {
    throw new BookApiError("INVALID_RESPONSE", "公开图书检索响应格式异常。");
  }
  return payload;
}
