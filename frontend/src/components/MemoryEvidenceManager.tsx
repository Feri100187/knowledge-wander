"use client";

import { useMemo } from "react";

import { getFeedbackKey, sortFeedbackRecords } from "@/lib/feedbackState";
import type { FeedbackRecord } from "@/types/feedback";

import styles from "./ExploreExperience.module.css";

interface MemoryEvidenceManagerProps {
  records: FeedbackRecord[];
  evidenceCount: number;
  isOpen: boolean;
  pending: Record<string, boolean>;
  errors: Record<string, string | null>;
  actionNotice: string | null;
  onToggle: () => void;
  onRemove: (record: FeedbackRecord) => void;
}

function getTargetTypeLabel(targetType: FeedbackRecord["target_type"]): string {
  return targetType === "book" ? "图书" : "知识节点";
}

export default function MemoryEvidenceManager({
  records,
  evidenceCount,
  isOpen,
  pending,
  errors,
  actionNotice,
  onToggle,
  onRemove,
}: MemoryEvidenceManagerProps) {
  const sortedRecords = useMemo(() => sortFeedbackRecords(records), [records]);

  return (
    <>
      <div className={styles.memoryInspectorHeader}>
        <div className={styles.memoryInspectorHeaderMain}>
          <h3>探索记忆</h3>
          <span>{evidenceCount} 条证据</span>
        </div>
        <button
          type="button"
          className={styles.memoryManageButton}
          onClick={onToggle}
          aria-expanded={isOpen}
          aria-controls="memory-evidence-panel"
        >
          {isOpen ? "收起管理" : "管理记忆"}
        </button>
      </div>

      {isOpen ? (
        <div id="memory-evidence-panel" className={styles.memoryEvidencePanel}>
          <div className={styles.memoryEvidenceHeading}>
            <span>记忆证据</span>
            <span>最近反馈优先</span>
          </div>
          {actionNotice ? (
            <p className={styles.memoryActionNotice} role="status">
              {actionNotice}
            </p>
          ) : null}
          {sortedRecords.length ? (
            <ul className={styles.memoryEvidenceList}>
              {sortedRecords.map((record) => {
                const key = getFeedbackKey(record.target_type, record.target_id);
                const isPending = pending[key] ?? false;
                const error = errors[key] ?? null;
                const targetMeta = [
                  getTargetTypeLabel(record.target_type),
                  record.target_domain,
                ]
                  .filter(Boolean)
                  .join(" · ");

                return (
                  <li key={key} className={styles.memoryEvidenceItem}>
                    <div className={styles.memoryEvidenceCopy}>
                      <div className={styles.memoryEvidenceTitle}>
                        <span aria-hidden="true">
                          {record.value === "like" ? "👍" : "👎"}
                        </span>
                        <strong>{record.target_label}</strong>
                      </div>
                      <span className={styles.memoryEvidenceMeta}>{targetMeta}</span>
                      {record.root_topic ? (
                        <span className={styles.memoryEvidenceOrigin}>
                          来自「{record.root_topic}」
                        </span>
                      ) : null}
                    </div>
                    <div className={styles.memoryEvidenceActions}>
                      <button
                        type="button"
                        className={styles.memoryRemoveButton}
                        onClick={() => onRemove(record)}
                        disabled={isPending}
                        aria-label={`取消对 ${record.target_label} 的记忆`}
                      >
                        {isPending ? "正在取消…" : error ? "重试" : "取消记忆"}
                      </button>
                      {error ? (
                        <span className={styles.memoryDeleteError} role="alert">
                          {error}
                        </span>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className={styles.memoryEvidenceEmpty}>暂无可管理的记忆证据。</p>
          )}
        </div>
      ) : null}
    </>
  );
}
