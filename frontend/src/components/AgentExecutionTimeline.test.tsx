import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AgentExecutionTimeline from "@/components/AgentExecutionTimeline";
import type { BookAgentStreamEvent } from "@/types/book";

const completeMetrics = {
  mode: "agent" as const,
  tool_used: true,
  queries: ["程序化叙事"],
  tool_trace: [],
  tool_calls: 1,
  tool_latency_ms: 1420,
  llm_rounds: 2,
  agent_total_latency_ms: 1800,
  fallback_used: false,
};

describe("AgentExecutionTimeline", () => {
  it("renders only safe path, tool, count, selection, and completion states", () => {
    const events: BookAgentStreamEvent[] = [
      { type: "agent_started" },
      { type: "path", path: ["游戏开发", "程序化叙事"] },
      { type: "tool_call", tool: "search_books", query: "程序化叙事" },
      { type: "tool_result", query: "程序化叙事", result_count: 8, duration_ms: 1420 },
      { type: "final_selection", book_count: 2 },
      { type: "complete", summary: "完成。", metrics: completeMetrics },
    ];

    render(
      <AgentExecutionTimeline
        events={events}
        phase="complete"
        currentPath={["游戏开发", "程序化叙事"]}
        nodeLabel="程序化叙事"
      />,
    );

    expect(screen.getByText("已读取当前路径")).toBeTruthy();
    expect(screen.getByText('search_books("程序化叙事")')).toBeTruthy();
    expect(screen.getByText(/找到 8 条真实书目/)).toBeTruthy();
    expect(screen.getByText("AI 选书完成")).toBeTruthy();
    expect(screen.queryByText(/Authorization|Cookie|ticket/)).toBeNull();
  });

  it("keeps the existing trace visible when a safe error event arrives", () => {
    const events: BookAgentStreamEvent[] = [
      { type: "agent_started" },
      { type: "path", path: ["游戏开发", "程序化叙事"] },
      { type: "tool_call", tool: "search_books", query: "程序化叙事" },
      { type: "error", code: "SEARCH_TIMEOUT", message: "公开图书检索超时，请稍后重试。" },
    ];

    render(
      <AgentExecutionTimeline
        events={events}
        phase="error"
        currentPath={["游戏开发", "程序化叙事"]}
        nodeLabel="程序化叙事"
      />,
    );

    expect(screen.getByText('search_books("程序化叙事")')).toBeTruthy();
    expect(screen.getByText("公开图书检索超时，请稍后重试。")).toBeTruthy();
  });
});
