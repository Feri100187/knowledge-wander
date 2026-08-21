import { afterEach, describe, expect, it, vi } from "vitest";

import { requestBookAgentStream } from "@/lib/bookApi";
import type { BookAgentRequest, BookAgentStreamEvent } from "@/types/book";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestBookAgentStream", () => {
  it("parses safe public-book events across stream chunks", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'event: tool_call\ndata: {"type":"tool_call","tool":"search_',
      'books","query":"程序化叙事"}\n\n',
      'event: tool_result\ndata: {"type":"tool_result","query":"程序化叙事","result_count":8,"duration_ms":1420}\n\n',
      'event: hidden\ndata: {"type":"hidden","content":"Authorization=secret"}\n\n',
      'event: complete\ndata: {"type":"complete","summary":"完成公开图书选择。","metrics":{"mode":"agent","tool_used":true,"queries":["程序化叙事"],"tool_trace":[],"tool_calls":1,"tool_latency_ms":1420,"llm_rounds":2,"agent_total_latency_ms":1800,"fallback_used":false}}\n\n',
    ];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body });
    vi.stubGlobal("fetch", fetchMock);

    const request: BookAgentRequest = {
      root_topic: "游戏开发",
      node_label: "程序化叙事",
      node_domain: "交互叙事",
      current_path: ["游戏开发", "程序化叙事"],
      surprise_level: 0.7,
    };
    const events: BookAgentStreamEvent[] = [];

    await requestBookAgentStream(request, (event) => events.push(event));

    expect(events.map((event) => event.type)).toEqual(["tool_call", "tool_result", "complete"]);
    expect(events[0]).toEqual({
      type: "tool_call",
      tool: "search_books",
      query: "程序化叙事",
    });
    expect(events[1]).toMatchObject({ type: "tool_result", result_count: 8, duration_ms: 1420 });
    expect(JSON.stringify(events)).not.toContain("Authorization");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/books/agent/discover/stream"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Accept: "text/event-stream" }),
        body: JSON.stringify(request),
      }),
    );
  });
});
