import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MemoryEvidenceManager from "@/components/MemoryEvidenceManager";
import { getFeedbackKey } from "@/lib/feedbackState";
import type { FeedbackRecord } from "@/types/feedback";

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

const records: FeedbackRecord[] = [
  makeRecord(),
  makeRecord({
    id: 2,
    target_type: "knowledge_node",
    target_id: "node-2",
    target_label: "视觉文化",
    target_domain: "文化研究",
    root_topic: "摄影史",
    value: "dislike",
    created_at: "2026-08-21T09:00:00.000Z",
    updated_at: "2026-08-21T09:00:00.000Z",
  }),
  makeRecord({
    id: 3,
    target_type: "book",
    target_id: "book-1",
    target_label: "Python 深度学习",
    target_domain: "人工智能",
    root_topic: "机器学习",
    created_at: "2026-08-21T10:00:00.000Z",
    updated_at: "2026-08-21T10:00:00.000Z",
  }),
];

function renderManager(overrides: Partial<React.ComponentProps<typeof MemoryEvidenceManager>> = {}) {
  const onRemove = vi.fn();
  const props: React.ComponentProps<typeof MemoryEvidenceManager> = {
    records,
    evidenceCount: records.length,
    isOpen: false,
    pending: {},
    errors: {},
    actionNotice: null,
    onToggle: vi.fn(),
    onRemove,
    ...overrides,
  };
  const view = render(<MemoryEvidenceManager {...props} />);
  return { ...view, onRemove, props };
}

describe("MemoryEvidenceManager", () => {
  it("keeps the evidence panel collapsed by default and shows all record types when opened", () => {
    const { props, rerender } = renderManager();

    expect(screen.getByRole("button", { name: "管理记忆" })).toBeTruthy();
    expect(screen.queryByText("记忆证据")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "管理记忆" }));
    expect(props.onToggle).toHaveBeenCalledTimes(1);
    props.isOpen = true;
    rerender(<MemoryEvidenceManager {...props} />);
    expect(screen.getByText("记忆证据")).toBeTruthy();
    expect(screen.getAllByText("👍")).toHaveLength(2);
    expect(screen.getAllByText("👎")).toHaveLength(1);
    expect(screen.getByText("知识节点 · 游戏设计")).toBeTruthy();
    expect(screen.getByText("图书 · 人工智能")).toBeTruthy();
    expect(screen.getByText("来自「游戏开发」")).toBeTruthy();
    expect(screen.getByText("来自「机器学习」")).toBeTruthy();
  });

  it("sorts evidence newest first and sends the complete record to remove", () => {
    const { onRemove } = renderManager({ isOpen: true });
    const titles = Array.from(document.querySelectorAll("li strong"), (node) => node.textContent);
    expect(titles).toEqual(["Python 深度学习", "视觉文化", "程序化叙事"]);

    fireEvent.click(
      screen.getByRole("button", { name: "取消对 Python 深度学习 的记忆" }),
    );
    expect(onRemove).toHaveBeenCalledWith(records[2]);
  });

  it("disables only the pending record and exposes a retry state after failure", () => {
    const error = "取消失败，请重试。";
    renderManager({
      isOpen: true,
      pending: { [getFeedbackKey("knowledge_node", "node-1")]: true },
      errors: { [getFeedbackKey("knowledge_node", "node-2")]: error },
    });

    const pendingButton = screen.getByRole("button", {
      name: "取消对 程序化叙事 的记忆",
    });
    const otherButton = screen.getByRole("button", {
      name: "取消对 视觉文化 的记忆",
    });
    expect(pendingButton).toHaveProperty("disabled", true);
    expect(pendingButton.textContent).toContain("正在取消");
    expect(otherButton).toHaveProperty("disabled", false);
    expect(screen.getByText(error)).toBeTruthy();
    expect(screen.getByRole("button", { name: "取消对 视觉文化 的记忆" }).textContent).toBe(
      "重试",
    );
  });
});
