import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BookAgentStreamEvent } from "@/types/book";
import type { ExploreResponse } from "@/types/explore";
import type { GraphEdgeData, GraphNodeData } from "@/types/graph";
import ExploreExperience from "@/components/ExploreExperience";

const mocks = vi.hoisted(() => ({
  requestExploration: vi.fn(),
  requestMemoryProfile: vi.fn(),
  getFeedback: vi.fn(),
  requestBookRecommendation: vi.fn(),
  requestBookAgentStream: vi.fn(),
  searchBooks: vi.fn(),
}));

vi.mock("@/lib/anonymousUser", () => ({
  getOrCreateAnonymousUserId: () => "progressive-user",
}));

vi.mock("@/lib/feedbackApi", () => ({
  getFeedback: mocks.getFeedback,
  setFeedback: vi.fn(),
  deleteFeedback: vi.fn(),
}));

vi.mock("@/lib/exploreApi", () => ({
  requestExploration: mocks.requestExploration,
  requestMemoryProfile: mocks.requestMemoryProfile,
}));

vi.mock("@/lib/bookApi", () => ({
  BookApiError: class BookApiError extends Error {},
  requestBookRecommendation: mocks.requestBookRecommendation,
  requestBookAgentStream: mocks.requestBookAgentStream,
  searchBooks: mocks.searchBooks,
}));

vi.mock("@/components/KnowledgeGraph/KnowledgeGraph", () => ({
  default: ({
    nodes,
    edges,
    onNodeSelect,
    generationPhase,
  }: {
    nodes: GraphNodeData[];
    edges: GraphEdgeData[];
    onNodeSelect: (node: GraphNodeData) => void;
    generationPhase: string;
  }) => (
    <div data-testid="graph-nodes">
      <div data-testid="graph-node-labels">{nodes.map((node) => node.label).join("|")}</div>
      <div data-testid="graph-edge-count">{edges.length}</div>
      <div data-testid="graph-phase">{generationPhase}</div>
      {nodes.map((node) => (
        <button
          type="button"
          key={node.id}
          data-testid={`select-${node.id}`}
          onClick={() => onNodeSelect(node)}
        >
          选择 {node.label}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("@/components/NodeDetailPanel", () => ({
  default: ({
    node,
    onContinueWander,
    onDiscoverBooks,
    books,
    bookError,
    onBookAgent,
    activeBookTab,
    onBookTabChange,
    bookAgentEvents,
    bookAgentBooks,
  }: {
    node: GraphNodeData | null;
    onContinueWander: () => void;
    onDiscoverBooks: (() => void) | null;
    books: unknown[] | null;
    bookError: string | null;
    onBookAgent: (() => void) | null;
    activeBookTab: string;
    onBookTabChange: (tab: "recommendations" | "agent" | "search") => void;
    bookAgentEvents: BookAgentStreamEvent[];
    bookAgentBooks: { book: { title: string }; reason: string }[];
  }) => (
    <div data-testid="detail-panel">
      {node ? <span data-testid="selected-node">{node.label}</span> : null}
      {node && !node.isRoot ? (
        <>
          <button type="button" data-testid="continue-wander" onClick={onContinueWander}>
            继续漫游
          </button>
          {onDiscoverBooks ? (
            <button type="button" data-testid="discover-books" onClick={onDiscoverBooks}>
              {bookError ? "重试相关图书" : books ? "查看相关图书" : "发现相关图书"}
            </button>
          ) : null}
          {onBookAgent ? (
            <button type="button" data-testid="book-agent" onClick={onBookAgent}>
              AI 选书
            </button>
          ) : null}
          <button
            type="button"
            data-testid="book-tab-agent"
            onClick={() => onBookTabChange("agent")}
          >
            切到 AI Tab
          </button>
        </>
      ) : null}
      <div data-testid="active-book-tab">{activeBookTab}</div>
      <div data-testid="agent-events">
        {bookAgentEvents.map((event, index) => `${index}:${event.type}`).join("|")}
      </div>
      <div data-testid="agent-books">
        {bookAgentBooks.map((item) => item.book.title).join("|")}
      </div>
    </div>
  ),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function response(
  nodes: Array<Partial<ExploreResponse["nodes"][number]> & { id: string; label: string }>,
): ExploreResponse {
  return {
    root: { id: "game-development", label: "游戏开发" },
    nodes: nodes.map((node, index) => ({
      id: node.id,
      label: node.label,
      domain: node.domain ?? "游戏设计",
      description: node.description ?? `${node.label} description`,
      connection: node.connection ?? `${node.label} connection`,
      surprise_score: node.surprise_score ?? 0.5 + index / 10,
    })),
    generation_source: "fallback",
    metadata: null,
  };
}

const publicBook = {
  id: "isbn:9780000000001",
  source: "openlibrary" as const,
  source_id: "/works/OL1W",
  title: "程序化叙事设计",
  authors: ["示例作者"],
  publisher: null,
  published_date: "2024",
  publication_year: "2024",
  isbn_10: null,
  isbn_13: "9780000000001",
  subjects: [],
  description: null,
  language: "chi",
  cover_url: null,
  info_url: "https://openlibrary.org/works/OL1W",
  preview_url: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getFeedback.mockResolvedValue({ feedbacks: [] });
  mocks.requestMemoryProfile.mockResolvedValue({ available: false, profile: null });
  mocks.requestBookRecommendation.mockResolvedValue({ books: [], error_code: null, message: null });
});

describe("progressive exploration presentation", () => {
  it("renders the optimistic root before the exploration API resolves", async () => {
    const pending = deferred<ExploreResponse>();
    mocks.requestExploration.mockReturnValue(pending.promise);

    render(<ExploreExperience />);
    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));

    expect(screen.getByTestId("graph-node-labels").textContent).toBe("游戏开发");
    expect(screen.getByText("AI 正在理解「游戏开发」……")).toBeTruthy();
    expect(screen.queryByText("程序化叙事")).toBeNull();

    pending.resolve(response([{ id: "node-1", label: "程序化叙事" }]));
    await waitFor(() => expect(screen.getByTestId("graph-node-labels").textContent).toContain("程序化叙事"));
  });

  it("reveals nodes and matching edges in order", async () => {
    mocks.requestExploration.mockResolvedValue(
      response([
        { id: "node-1", label: "程序化叙事" },
        { id: "node-2", label: "交互叙事" },
        { id: "node-3", label: "程序化生成" },
      ]),
    );

    render(<ExploreExperience />);
    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));

    await waitFor(() => {
      expect(screen.getByTestId("graph-node-labels").textContent).toBe("游戏开发|程序化叙事");
      expect(screen.getByTestId("graph-edge-count").textContent).toBe("1");
    });
    expect(screen.getByTestId("graph-node-labels").textContent).not.toContain("交互叙事");

    await waitFor(
      () => expect(screen.getByTestId("graph-node-labels").textContent).toBe("游戏开发|程序化叙事|交互叙事"),
      { timeout: 700 },
    );
    expect(screen.getByTestId("graph-edge-count").textContent).toBe("2");

    await waitFor(
      () => expect(screen.getByTestId("graph-node-labels").textContent).toBe("游戏开发|程序化叙事|交互叙事|程序化生成"),
      { timeout: 700 },
    );
    expect(screen.getByTestId("graph-edge-count").textContent).toBe("3");
  });

  it("uses the same reveal path for continue wander and keeps the root after an error", async () => {
    mocks.requestExploration
      .mockResolvedValueOnce(response([{ id: "node-1", label: "程序化叙事" }]))
      .mockResolvedValueOnce(response([
        { id: "node-2", label: "互动设计" },
        { id: "node-3", label: "叙事结构" },
      ]))
      .mockRejectedValueOnce(new Error("offline"));

    render(<ExploreExperience />);
    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));
    await waitFor(() => expect(screen.getByTestId("select-node-1")).toBeTruthy());
    fireEvent.click(screen.getByTestId("select-node-1"));
    fireEvent.click(screen.getByTestId("continue-wander"));

    await waitFor(() => expect(screen.getByTestId("graph-node-labels").textContent).toContain("互动设计"));
    expect(screen.getByTestId("graph-node-labels").textContent).not.toContain("叙事结构");
    await waitFor(
      () => expect(screen.getByTestId("graph-node-labels").textContent).toContain("叙事结构"),
      { timeout: 700 },
    );

    await waitFor(() => expect(screen.getByRole("button", { name: "开始漫游" })).toHaveProperty("disabled", false));
    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("暂时无法连接探索服务"));
    expect(screen.getByTestId("graph-node-labels").textContent).toBe("游戏开发");
  });

  it("switches public-book modes and does not repeat loaded requests", async () => {
    mocks.requestExploration.mockResolvedValue(response([{ id: "node-1", label: "程序化叙事" }]));
    mocks.requestBookRecommendation.mockResolvedValue({
      books: [{ ...publicBook, reason: "相关图书", relevance_score: 0.9 }],
      error_code: null,
      message: null,
    });

    render(<ExploreExperience />);
    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));
    await waitFor(() => expect(screen.getByTestId("select-node-1")).toBeTruthy());
    fireEvent.click(screen.getByTestId("select-node-1"));

    expect(screen.getByTestId("active-book-tab").textContent).toBe("recommendations");
    fireEvent.click(screen.getByTestId("discover-books"));
    await waitFor(() => expect(mocks.requestBookRecommendation).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTestId("discover-books"));
    expect(mocks.requestBookRecommendation).toHaveBeenCalledTimes(1);

    mocks.requestBookAgentStream.mockImplementation(
      async (_request: unknown, onEvent: (event: BookAgentStreamEvent) => void) => {
        onEvent({ type: "complete", summary: "AI 选书完成。", metrics: {
          mode: "agent",
          tool_used: true,
          queries: ["程序化叙事"],
          tool_trace: [],
          tool_calls: 1,
          tool_latency_ms: 120,
          llm_rounds: 1,
          agent_total_latency_ms: 180,
          fallback_used: false,
        } });
      },
    );
    fireEvent.click(screen.getByTestId("book-agent"));
    expect(screen.getByTestId("active-book-tab").textContent).toBe("agent");
    await waitFor(() => expect(mocks.requestBookAgentStream).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTestId("book-agent"));
    expect(mocks.requestBookAgentStream).toHaveBeenCalledTimes(1);
  });

  it("shows safe stream events and appends verified books", async () => {
    mocks.requestExploration.mockResolvedValue(response([{ id: "node-1", label: "程序化叙事" }]));
    mocks.requestBookAgentStream.mockImplementation(
      async (_request: unknown, onEvent: (event: BookAgentStreamEvent) => void) => {
        onEvent({ type: "agent_started" });
        onEvent({ type: "path", path: ["游戏开发", "程序化叙事"] });
        onEvent({ type: "tool_call", tool: "search_books", query: "程序化叙事" });
        onEvent({ type: "tool_result", query: "程序化叙事", result_count: 8, duration_ms: 1420 });
        onEvent({ type: "final_selection", book_count: 1 });
        onEvent({ type: "book", book: publicBook, reason: "沿当前路径继续阅读。" });
        onEvent({ type: "complete", summary: "完成公开图书选择。", metrics: {
          mode: "agent",
          tool_used: true,
          queries: ["程序化叙事"],
          tool_trace: [],
          tool_calls: 1,
          tool_latency_ms: 1420,
          llm_rounds: 2,
          agent_total_latency_ms: 1800,
          fallback_used: false,
        } });
      },
    );

    render(<ExploreExperience />);
    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));
    await waitFor(() => expect(screen.getByTestId("select-node-1")).toBeTruthy());
    fireEvent.click(screen.getByTestId("select-node-1"));
    fireEvent.click(screen.getByTestId("book-agent"));

    await waitFor(() => expect(screen.getByTestId("agent-events").textContent).toContain("tool_call"));
    await waitFor(() => expect(screen.getByTestId("agent-books").textContent).toContain("程序化叙事设计"));
  });
});
