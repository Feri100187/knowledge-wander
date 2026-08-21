"use client";

import type {
  BookAgentPhase,
  BookAgentStreamEvent,
} from "@/types/book";

import styles from "./AgentExecutionTimeline.module.css";

interface AgentExecutionTimelineProps {
  events: BookAgentStreamEvent[];
  phase: BookAgentPhase;
  currentPath: string[];
  nodeLabel: string;
}

function formatDuration(durationMs: number | null): string {
  if (durationMs == null) {
    return "耗时未知";
  }
  return `${Math.round(durationMs)}ms`;
}

export default function AgentExecutionTimeline({
  events,
  phase,
  currentPath,
  nodeLabel,
}: AgentExecutionTimelineProps) {
  const pathEvent = events.find((event) => event.type === "path");
  const toolCalls = events.filter((event) => event.type === "tool_call");
  const toolResults = events.filter((event) => event.type === "tool_result");
  const selectionEvent = events.find((event) => event.type === "final_selection");
  const completeEvent = events.find((event) => event.type === "complete");
  const errorEvent = events.find((event) => event.type === "error");
  const path = pathEvent?.type === "path" ? pathEvent.path : currentPath;

  return (
    <ol className={styles.timeline} aria-label="AI 选书智能体执行步骤">
      <li className={pathEvent ? styles.complete : styles.active}>
        <span className={styles.marker}>{pathEvent ? "✓" : "●"}</span>
        <div>
          <strong>{pathEvent ? "已读取当前路径" : "分析当前知识路径……"}</strong>
          <span>{path.length ? path.join(" → ") : nodeLabel}</span>
        </div>
      </li>

      {pathEvent && !toolCalls.length && !completeEvent && !errorEvent ? (
        <li className={styles.active}>
          <span className={styles.marker}>●</span>
          <div>
            <strong>正在决定图书检索词……</strong>
            <span>寻找能连接当前知识路径的公开书目</span>
          </div>
        </li>
      ) : null}

      {toolCalls.map((toolCall, index) => {
        if (toolCall.type !== "tool_call") {
          return null;
        }
        const result = toolResults[index];
        return (
          <li key={`${toolCall.query}-${index}`} className={result ? styles.complete : styles.active}>
            <span className={styles.marker}>{result ? "✓" : "●"}</span>
            <div>
              <strong>{result ? "已调用公开图书数据库" : "调用公开图书数据库"}</strong>
              <code>search_books(&quot;{toolCall.query}&quot;)</code>
              {result?.type === "tool_result" ? (
                <span>
                  找到 {result.result_count} 条真实书目 · {formatDuration(result.duration_ms)}
                </span>
              ) : (
                <span>正在查询 Open Library / Google Books……</span>
              )}
            </div>
          </li>
        );
      })}

      {selectionEvent && !completeEvent ? (
        <li className={styles.active}>
          <span className={styles.marker}>●</span>
          <div>
            <strong>AI 正在从真实结果中选择值得继续阅读的书……</strong>
            <span>已验证结果，准备展示阅读路径</span>
          </div>
        </li>
      ) : null}

      {completeEvent?.type === "complete" ? (
        <li className={styles.complete}>
          <span className={styles.marker}>✓</span>
          <div>
            <strong>AI 选书完成</strong>
            <span>
              {completeEvent.metrics.fallback_used
                ? "已使用稳定公开图书推荐模式"
                : `已从真实结果中选择 ${selectionEvent?.type === "final_selection" ? selectionEvent.book_count : 0} 本书`}
            </span>
          </div>
        </li>
      ) : null}

      {errorEvent?.type === "error" ? (
        <li className={styles.error}>
          <span className={styles.marker}>!</span>
          <div>
            <strong>图书检索未完成</strong>
            <span>{errorEvent.message}</span>
          </div>
        </li>
      ) : null}

      {!events.length && phase !== "idle" ? (
        <li className={styles.active}>
          <span className={styles.marker}>●</span>
          <div>
            <strong>分析当前知识路径……</strong>
            <span>{currentPath.join(" → ") || nodeLabel}</span>
          </div>
        </li>
      ) : null}
    </ol>
  );
}
