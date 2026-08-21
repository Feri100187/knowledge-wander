import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { BookAgentPhase, BookWorkspaceTab, PublicBook } from "@/types/book";
import type { GraphNodeData } from "@/types/graph";
import LibraryWorkspace from "@/components/LibraryWorkspace";

const node: GraphNodeData = {
  id: "node-1",
  label: "程序化叙事",
  domain: "游戏设计",
  description: "description",
  connection: "connection",
  surpriseScore: 0.7,
  depth: 1,
  isRoot: false,
  expanded: false,
};

const book: PublicBook = {
  id: "isbn:9780000000001",
  source: "openlibrary",
  source_id: "/works/OL1W",
  title: "程序化叙事设计",
  authors: ["示例作者"],
  publisher: "示例出版社",
  published_date: "2024",
  publication_year: "2024",
  isbn_10: null,
  isbn_13: "9780000000001",
  subjects: ["叙事"],
  description: "公开书目简介。",
  language: "chi",
  cover_url: null,
  info_url: "https://openlibrary.org/works/OL1W",
  preview_url: null,
};

function WorkspaceHarness({
  root = false,
  agentPhase = "complete",
  agentError = null,
}: {
  root?: boolean;
  agentPhase?: BookAgentPhase;
  agentError?: string | null;
}) {
  const [activeTab, setActiveTab] = useState<BookWorkspaceTab>("recommendations");
  const workspaceRef = useRef<HTMLElement>(null);
  const agentBook = { book, reason: "与当前路径相连。" };

  return (
    <LibraryWorkspace
      node={root ? { ...node, id: "root", label: "游戏开发", isRoot: true } : node}
      currentPath={["游戏开发", node.label]}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      workspaceRef={workspaceRef}
      onDiscoverBooks={vi.fn()}
      isDiscoveringBooks={false}
      books={[{ ...book, reason: "相关图书", relevance_score: 0.9 }]}
      bookError={null}
      onRetryBooks={vi.fn()}
      onBookAgent={vi.fn()}
      isBookAgentRunning={false}
      bookAgentResult={null}
      bookAgentEvents={[]}
      bookAgentBooks={[agentBook]}
      bookAgentPhase={agentPhase}
      bookAgentError={agentError}
      onRetryBookAgent={vi.fn()}
      bookFeedback={{}}
      onBookFeedback={vi.fn()}
      isBookFeedbackPending={{}}
      bookFeedbackErrors={{}}
      onRetryBookFeedback={vi.fn()}
      bookSearchQuery="Python"
      onBookSearchQueryChange={vi.fn()}
      isBookSearching={false}
      onBookSearch={vi.fn()}
      bookSearchResults={null}
      bookSearchError={null}
    />
  );
}

describe("LibraryWorkspace public-book modes", () => {
  it("shows only the selected public-book mode while retaining the other results", async () => {
    render(<WorkspaceHarness />);

    const recommendations = document.getElementById("book-panel-recommendations");
    const agent = document.getElementById("book-panel-agent");
    const search = document.getElementById("book-panel-search");
    expect(recommendations?.hasAttribute("hidden")).toBe(false);
    expect(agent?.hasAttribute("hidden")).toBe(true);
    expect(search?.hasAttribute("hidden")).toBe(true);
    await waitFor(() => expect(screen.getAllByText("程序化叙事设计").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("tab", { name: /AI 选书/ }));
    expect(recommendations?.hasAttribute("hidden")).toBe(true);
    expect(agent?.hasAttribute("hidden")).toBe(false);
    expect(search?.hasAttribute("hidden")).toBe(true);
    await waitFor(() => expect(screen.getAllByText("程序化叙事设计").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("tab", { name: /图书检索/ }));
    expect(recommendations?.hasAttribute("hidden")).toBe(true);
    expect(agent?.hasAttribute("hidden")).toBe(true);
    expect(search?.hasAttribute("hidden")).toBe(false);
    expect(screen.getByDisplayValue("Python")).toBeTruthy();
  });

  it("only exposes search for the root node", () => {
    render(<WorkspaceHarness root />);

    expect(screen.queryByRole("tab", { name: /相关图书/ })).toBeNull();
    expect(screen.queryByRole("tab", { name: /AI 选书/ })).toBeNull();
    expect(screen.getByText("检索公开图书")).toBeTruthy();
  });

  it("shows a failed execution state instead of an active badge", () => {
    render(<WorkspaceHarness agentPhase="error" agentError="公开图书检索超时，请稍后重试。" />);
    fireEvent.click(screen.getByRole("tab", { name: /AI 选书/ }));

    expect(screen.getByText("图书检索未完成")).toBeTruthy();
    expect(screen.queryByText("实时执行中")).toBeNull();
  });
});
