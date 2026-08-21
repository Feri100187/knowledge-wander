export type BookSource = "openlibrary" | "google_books";

export interface PublicBook {
  id: string;
  source: BookSource;
  source_id: string;
  title: string;
  authors: string[];
  publisher: string | null;
  published_date: string | null;
  publication_year: string | null;
  isbn_10: string | null;
  isbn_13: string | null;
  subjects: string[];
  description: string | null;
  language: string | null;
  cover_url: string | null;
  info_url: string | null;
  preview_url: string | null;
}

export interface BookRecommendation extends PublicBook {
  reason: string;
  relevance_score: number;
}

export interface BookRecommendRequest {
  root_topic: string;
  node_label: string;
  node_domain: string;
  surprise_level: number;
  language?: string | null;
}

export interface BookRecommendResponse {
  data_source: string;
  data_notice: string;
  query: string;
  books: BookRecommendation[];
  error_code: string | null;
  message: string | null;
}

export interface BookSearchRequest {
  q: string;
  language?: string;
  limit?: number;
  page?: number;
}

export interface BookSearchResponse {
  data_source: string;
  query: string;
  page: number;
  page_size: number;
  total: number;
  books: PublicBook[];
  error_code: string | null;
  message: string | null;
}

export type BookWorkspaceTab = "recommendations" | "agent" | "search";

export interface BookAgentRequest {
  root_topic: string;
  node_label: string;
  node_domain: string;
  current_path: string[];
  surprise_level: number;
  language?: string | null;
}

export interface BookAgentToolTrace {
  tool: "search_books";
  query: string;
  language: string | null;
  result_count: number;
  duration_ms: number | null;
}

export interface BookAgentBook {
  book: PublicBook;
  reason: string;
}

export interface BookAgentResponse {
  mode: "agent" | "fallback";
  tool_used: boolean;
  summary: string;
  queries: string[];
  books: BookAgentBook[];
  tool_trace: BookAgentToolTrace[];
  tool_calls: number;
  tool_latency_ms: number;
  llm_rounds: number;
  agent_total_latency_ms: number;
  fallback_used: boolean;
}

export type BookAgentPhase =
  | "idle"
  | "analyzing"
  | "tool_call"
  | "searching"
  | "selecting"
  | "revealing_books"
  | "complete"
  | "error";

export interface BookAgentStreamMetrics {
  mode: "agent" | "fallback";
  tool_used: boolean;
  queries: string[];
  tool_trace: BookAgentToolTrace[];
  tool_calls: number;
  tool_latency_ms: number;
  llm_rounds: number;
  agent_total_latency_ms: number;
  fallback_used: boolean;
}

export type BookAgentStreamEvent =
  | { type: "agent_started" }
  | { type: "path"; path: string[] }
  | { type: "tool_call"; tool: "search_books"; query: string }
  | {
      type: "tool_result";
      query: string;
      result_count: number;
      duration_ms: number | null;
    }
  | { type: "final_selection"; book_count: number }
  | { type: "book"; book: PublicBook; reason: string }
  | {
      type: "complete";
      summary: string;
      metrics: BookAgentStreamMetrics;
    }
  | { type: "error"; message: string; code?: string };
