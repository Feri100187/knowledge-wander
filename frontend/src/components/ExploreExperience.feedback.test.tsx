import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FeedbackRecord } from "@/types/feedback";
import type { MemoryProfileResponse } from "@/types/explore";

const mocks = vi.hoisted(() => ({
  getFeedback: vi.fn(),
  setFeedback: vi.fn(),
  deleteFeedback: vi.fn(),
  requestMemoryProfile: vi.fn(),
  requestExploration: vi.fn(),
  requestBookAgentStream: vi.fn(),
  requestBookRecommendation: vi.fn(),
  searchBooks: vi.fn(),
}));

vi.mock("@/lib/anonymousUser", () => ({
  getOrCreateAnonymousUserId: () => "user-1",
}));

vi.mock("@/lib/feedbackApi", () => ({
  getFeedback: mocks.getFeedback,
  setFeedback: mocks.setFeedback,
  deleteFeedback: mocks.deleteFeedback,
}));

vi.mock("@/lib/exploreApi", () => ({
  requestExploration: mocks.requestExploration,
  requestMemoryProfile: mocks.requestMemoryProfile,
}));

vi.mock("@/lib/bookApi", () => ({
  BookApiError: class BookApiError extends Error {},
  requestBookAgentStream: mocks.requestBookAgentStream,
  requestBookRecommendation: mocks.requestBookRecommendation,
  searchBooks: mocks.searchBooks,
}));

vi.mock("@/components/KnowledgeGraph/KnowledgeGraph", () => ({
  default: ({ onNodeSelect }: { onNodeSelect: (node: {
    id: string;
    label: string;
    domain: string;
    description: string;
    connection: string;
    surpriseScore: number;
    depth: number;
    isRoot: boolean;
    expanded: boolean;
  }) => void }) => {
    const node = {
      id: "node-1",
      label: "程序化叙事",
      domain: "游戏设计",
      description: "description",
      connection: "connection",
      surpriseScore: 0.5,
      depth: 1,
      isRoot: false,
      expanded: false,
    };
    return (
      <button type="button" data-testid="select-node" onClick={() => onNodeSelect(node)}>
        选择节点
      </button>
    );
  },
}));

vi.mock("@/components/NodeDetailPanel", () => ({
  default: ({
    node,
    nodeFeedback,
    onNodeFeedback,
  }: {
    node: { label: string } | null;
    nodeFeedback: "like" | "dislike" | null;
    onNodeFeedback: (value: "like" | "dislike") => void;
  }) => (
    <div data-testid="node-detail-panel">
      {node ? <span data-testid="node-feedback-value">{nodeFeedback ?? "none"}</span> : null}
      {node ? (
        <>
          <button type="button" data-testid="node-like" onClick={() => onNodeFeedback("like")}>
            节点喜欢
          </button>
          <button
            type="button"
            data-testid="node-dislike"
            onClick={() => onNodeFeedback("dislike")}
          >
            节点不喜欢
          </button>
        </>
      ) : null}
    </div>
  ),
}));

import ExploreExperience from "@/components/ExploreExperience";

function makeRecord(overrides: Partial<FeedbackRecord> = {}): FeedbackRecord {
  return {
    id: 1,
    anonymous_user_id: "user-1",
    target_type: "knowledge_node",
    target_id: "node-1",
    target_label: "程序化叙事",
    target_domain: "游戏设计",
    root_topic: "游戏开发",
    value: "like",
    surprise_level: 0.5,
    generation_source: "fallback",
    created_at: "2026-08-21T08:00:00.000Z",
    updated_at: "2026-08-21T08:00:00.000Z",
    ...overrides,
  };
}

function makeProfile(evidenceCount: number): MemoryProfileResponse {
  return {
    available: evidenceCount > 0,
    profile: evidenceCount > 0
      ? {
          anonymous_user_id: "user-1",
          preferred_domains: ["游戏设计"],
          disliked_domains: [],
          liked_concepts: ["程序化叙事"],
          disliked_concepts: [],
          preferred_surprise_level: 0.5,
          evidence_count: evidenceCount,
          updated_at: "2026-08-21T08:00:00.000Z",
          memory_signature: "signature",
        }
      : null,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requestMemoryProfile.mockResolvedValue(makeProfile(3));
  mocks.requestExploration.mockResolvedValue({
    root: { id: "root-1", label: "游戏开发" },
    nodes: [
      {
        id: "node-1",
        label: "程序化叙事",
        domain: "游戏设计",
        description: "description",
        connection: "connection",
        surprise_score: 0.5,
      },
    ],
    generation_source: "fallback",
    metadata: null,
  });
  mocks.getFeedback.mockResolvedValue({
    feedbacks: [
      makeRecord(),
      makeRecord({
        id: 2,
        target_type: "knowledge_node",
        target_id: "node-2",
        target_label: "视觉文化",
        target_domain: "文化研究",
        value: "dislike",
      }),
      makeRecord({
        id: 3,
        target_type: "book",
        target_id: "book-1",
        target_label: "Python 深度学习",
        target_domain: "人工智能",
      }),
    ],
  });
  mocks.deleteFeedback.mockResolvedValue(undefined);
  mocks.setFeedback.mockResolvedValue(makeRecord({ updated_at: "2026-08-21T09:00:00.000Z" }));
});

describe("ExploreExperience feedback synchronization", () => {
  it("loads three records, deletes one with the API arguments, and refreshes memory", async () => {
    render(<ExploreExperience />);

    await waitFor(() => expect(screen.getByText("记忆已应用 · 3 条证据")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "管理记忆" }));
    expect(screen.getAllByRole("button", { name: /取消对/ })).toHaveLength(3);

    fireEvent.click(
      screen.getByRole("button", { name: "取消对 Python 深度学习 的记忆" }),
    );

    await waitFor(() => {
      expect(mocks.deleteFeedback).toHaveBeenCalledWith("book", "book-1", "user-1");
      expect(screen.queryByText("Python 深度学习")).toBeNull();
    });
    expect(mocks.requestMemoryProfile).toHaveBeenCalledTimes(2);
    expect(screen.getAllByRole("button", { name: /取消对/ })).toHaveLength(2);
  });

  it("keeps a failed record and shows a retry message", async () => {
    mocks.deleteFeedback.mockRejectedValueOnce(new Error("network error"));
    render(<ExploreExperience />);

    await waitFor(() => expect(screen.getByText("记忆已应用 · 3 条证据")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "管理记忆" }));
    fireEvent.click(
      screen.getByRole("button", { name: "取消对 Python 深度学习 的记忆" }),
    );

    await waitFor(() => expect(screen.getByText("取消失败，请重试。")).toBeTruthy());
    expect(screen.getByText("Python 深度学习")).toBeTruthy();
    expect(mocks.requestMemoryProfile).toHaveBeenCalledTimes(1);
  });

  it("updates the manager when node feedback is added, changed, and removed in place", async () => {
    const initialRecord = makeRecord();
    const dislikedRecord = makeRecord({
      value: "dislike",
      updated_at: "2026-08-21T09:00:00.000Z",
    });
    mocks.getFeedback.mockResolvedValue({ feedbacks: [initialRecord] });
    mocks.requestMemoryProfile.mockResolvedValue(makeProfile(1));
    mocks.setFeedback.mockResolvedValue(dislikedRecord);

    render(<ExploreExperience />);
    await waitFor(() => expect(screen.getByText("记忆已应用 · 1 条证据")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "开始漫游" }));
    await waitFor(() => expect(screen.getByTestId("select-node")).toBeTruthy());
    fireEvent.click(screen.getByTestId("select-node"));
    expect(screen.getByTestId("node-feedback-value").textContent).toBe("like");

    fireEvent.click(screen.getByTestId("node-dislike"));
    await waitFor(() => {
      expect(mocks.setFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          target_type: "knowledge_node",
          target_id: "node-1",
          value: "dislike",
        }),
      );
      expect(screen.getByTestId("node-feedback-value").textContent).toBe("dislike");
    });

    fireEvent.click(screen.getByRole("button", { name: "管理记忆" }));
    expect(screen.getByText("👎")).toBeTruthy();
    fireEvent.click(screen.getByTestId("node-dislike"));

    await waitFor(() => {
      expect(mocks.deleteFeedback).toHaveBeenCalledWith(
        "knowledge_node",
        "node-1",
        "user-1",
      );
      expect(screen.getByTestId("node-feedback-value").textContent).toBe("none");
      expect(screen.queryByText("程序化叙事")).toBeNull();
    });
  });
});
