"use client";

import type { GraphGenerationState } from "@/types/graph";

import styles from "./GraphGenerationStatus.module.css";

interface GraphGenerationStatusProps {
  state: GraphGenerationState;
  subjectLabel: string;
  isExpansion: boolean;
  revealedCount: number;
  totalCount: number | null;
  error: string | null;
  onRetry?: () => void;
}

export default function GraphGenerationStatus({
  state,
  subjectLabel,
  isExpansion,
  revealedCount,
  totalCount,
  error,
  onRetry,
}: GraphGenerationStatusProps) {
  if (state === "idle") {
    return null;
  }

  const isActive = state === "waiting" || state === "revealing" || state === "settling";
  const countLabel = totalCount == null
    ? "已建立起点"
    : `${revealedCount} / ${totalCount} 条分支`;

  let title = "已生成知识路径";
  let detail = totalCount == null ? "" : countLabel;
  if (state === "waiting") {
    title = `AI 正在理解「${subjectLabel}」……`;
    detail = isExpansion ? "准备从当前节点寻找新的连接" : "已建立起点，正在寻找第一条知识连接";
  } else if (state === "revealing") {
    title = isExpansion ? "正在展开知识分支……" : "正在寻找跨领域连接……";
    detail = countLabel;
  } else if (state === "settling") {
    title = "正在让知识地图稳定下来……";
    detail = countLabel;
  } else if (state === "complete") {
    title = `已生成 ${totalCount ?? revealedCount} 条知识路径`;
    detail = isExpansion ? "当前节点已展开" : "知识地图已就绪";
  } else if (state === "error") {
    title = "生成知识连接失败";
    detail = error ?? "请重试，已出现的知识节点会保留";
  }

  return (
    <div
      className={`${styles.status} ${isActive ? styles.active : ""} ${state === "complete" ? styles.complete : ""} ${state === "error" ? styles.error : ""}`}
      role="status"
      aria-live="polite"
    >
      <span className={styles.dot} aria-hidden="true" />
      <div className={styles.copy}>
        <strong>{title}</strong>
        {detail ? <span>{detail}</span> : null}
      </div>
      {state === "error" && onRetry ? (
        <button type="button" onClick={onRetry} className={styles.retryButton}>
          重试
        </button>
      ) : null}
    </div>
  );
}
