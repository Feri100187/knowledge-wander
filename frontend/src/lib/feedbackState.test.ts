import { describe, expect, it } from "vitest";

import {
  buildFeedbackMap,
  removeFeedbackRecord,
  sortFeedbackRecords,
  upsertFeedbackRecord,
} from "@/lib/feedbackState";
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

describe("feedback local state helpers", () => {
  it("builds a feedback map for both nodes and books", () => {
    const records = [
      makeRecord(),
      makeRecord({
        id: 2,
        target_type: "book",
        target_id: "book-1",
        target_label: "Python 深度学习",
        target_domain: "人工智能",
        value: "dislike",
      }),
    ];

    expect(buildFeedbackMap(records)).toEqual({
      "knowledge_node:node-1": "like",
      "book:book-1": "dislike",
    });
  });

  it("replaces the existing target record and appends new targets", () => {
    const existing = makeRecord();
    const changed = makeRecord({
      id: 3,
      value: "dislike",
      updated_at: "2026-08-21T09:00:00.000Z",
    });
    const added = makeRecord({
      id: 4,
      target_id: "node-2",
      target_label: "视觉文化",
    });

    const replaced = upsertFeedbackRecord([existing], changed);
    expect(replaced).toHaveLength(1);
    expect(replaced[0]).toEqual(changed);

    expect(upsertFeedbackRecord(replaced, added)).toEqual([changed, added]);
  });

  it("removes only the requested target record", () => {
    const node = makeRecord();
    const book = makeRecord({
      id: 2,
      target_type: "book",
      target_id: "book-1",
      target_label: "Python 深度学习",
    });

    expect(removeFeedbackRecord([node, book], "knowledge_node", "node-1")).toEqual([
      book,
    ]);
  });

  it("sorts by updated time, then created time", () => {
    const olderUpdated = makeRecord({
      id: 1,
      target_id: "node-1",
      target_label: "较早更新",
      created_at: "2026-08-21T10:00:00.000Z",
      updated_at: "2026-08-21T10:00:00.000Z",
    });
    const newerCreated = makeRecord({
      id: 2,
      target_id: "node-2",
      target_label: "同次更新较新创建",
      created_at: "2026-08-21T11:00:00.000Z",
      updated_at: "2026-08-21T10:00:00.000Z",
    });
    const newestUpdated = makeRecord({
      id: 3,
      target_id: "node-3",
      target_label: "最近更新",
      created_at: "2026-08-21T09:00:00.000Z",
      updated_at: "2026-08-21T12:00:00.000Z",
    });

    expect(sortFeedbackRecords([olderUpdated, newerCreated, newestUpdated]).map(
      (record) => record.target_label,
    )).toEqual(["最近更新", "同次更新较新创建", "较早更新"]);
  });
});
