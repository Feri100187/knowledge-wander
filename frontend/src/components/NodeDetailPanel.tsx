"use client";

import type { RefObject } from "react";

import type { GraphNodeData } from "@/types/graph";
import type { FeedbackValue } from "@/types/feedback";
import type {
  BookAgentBook,
  BookAgentPhase,
  BookAgentResponse,
  BookAgentStreamEvent,
  BookRecommendation,
  BookSearchResponse,
  BookWorkspaceTab,
} from "@/types/book";

import BookSearchPanel from "@/components/BookSearchPanel";
import LibraryWorkspace from "@/components/LibraryWorkspace";
import styles from "./NodeDetailPanel.module.css";

interface NodeDetailPanelProps {
  node: GraphNodeData | null;
  currentPath: string[];
  isExpanding: boolean;
  expandError: string | null;
  maxNodesReached: boolean;
  onContinueWander: () => void;
  onRetry: () => void;
  onDiscoverBooks: (() => void) | null;
  isDiscoveringBooks: boolean;
  books: BookRecommendation[] | null;
  bookError: string | null;
  onRetryBooks: () => void;
  onBookAgent: (() => void) | null;
  isBookAgentRunning: boolean;
  bookAgentResult: BookAgentResponse | null;
  bookAgentEvents: BookAgentStreamEvent[];
  bookAgentBooks: BookAgentBook[];
  bookAgentPhase: BookAgentPhase;
  bookAgentError: string | null;
  onRetryBookAgent: () => void;
  activeBookTab: BookWorkspaceTab;
  onBookTabChange: (tab: BookWorkspaceTab) => void;
  libraryWorkspaceRef: RefObject<HTMLElement | null>;
  nodeFeedback: FeedbackValue | null;
  onNodeFeedback: (value: FeedbackValue) => void;
  isNodeFeedbackPending: boolean;
  nodeFeedbackError: string | null;
  onRetryNodeFeedback: () => void;
  bookFeedback: Record<string, FeedbackValue>;
  onBookFeedback: (bookId: string, value: FeedbackValue) => void;
  isBookFeedbackPending: Record<string, boolean>;
  bookFeedbackErrors: Record<string, string | null>;
  onRetryBookFeedback: (bookId: string) => void;
  bookSearchQuery: string;
  onBookSearchQueryChange: (value: string) => void;
  isBookSearching: boolean;
  onBookSearch: () => void;
  bookSearchResults: BookSearchResponse | null;
  bookSearchError: string | null;
}

export default function NodeDetailPanel({
  node,
  currentPath,
  isExpanding,
  expandError,
  maxNodesReached,
  onContinueWander,
  onRetry,
  onDiscoverBooks,
  isDiscoveringBooks,
  books,
  bookError,
  onRetryBooks,
  onBookAgent,
  isBookAgentRunning,
  bookAgentResult,
  bookAgentEvents,
  bookAgentBooks,
  bookAgentPhase,
  bookAgentError,
  onRetryBookAgent,
  activeBookTab,
  onBookTabChange,
  libraryWorkspaceRef,
  nodeFeedback,
  onNodeFeedback,
  isNodeFeedbackPending,
  nodeFeedbackError,
  onRetryNodeFeedback,
  bookFeedback,
  onBookFeedback,
  isBookFeedbackPending,
  bookFeedbackErrors,
  onRetryBookFeedback,
  bookSearchQuery,
  onBookSearchQueryChange,
  isBookSearching,
  onBookSearch,
  bookSearchResults,
  bookSearchError,
}: NodeDetailPanelProps) {
  if (!node) {
    return (
      <div className={styles.panel}>
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>◎</span>
          <p>点击图谱中的知识节点，<br />查看详情并继续漫游。</p>
        </div>
        <BookSearchPanel
          query={bookSearchQuery}
          onQueryChange={onBookSearchQueryChange}
          isSearching={isBookSearching}
          onSearch={onBookSearch}
          results={bookSearchResults}
          error={bookSearchError}
        />
      </div>
    );
  }

  const isRoot = node.isRoot;
  const hasBookAgentResult =
    Boolean(bookAgentResult) ||
    bookAgentEvents.length > 0 ||
    bookAgentBooks.length > 0;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.domainBadge}>
          {isRoot ? "探索起点" : node.domain}
        </span>
        <h3 className={styles.title}>{node.label}</h3>
      </div>

      {!isRoot && (
        <>
          {currentPath.length > 1 ? (
            <div className={styles.currentPath} aria-label="当前知识路径">
              <span>当前路径</span>
              <p>{currentPath.join(" → ")}</p>
            </div>
          ) : null}

          <p className={styles.description}>{node.description}</p>

          <div className={styles.connectionBox}>
            <span>为什么它与你当前路径有关？</span>
            <p>{node.connection}</p>
          </div>

          <div className={styles.scoreRow}>
            <span>意外度</span>
            <div className={styles.scoreTrack} aria-hidden="true">
              <span
                style={{
                  width: `${Math.round(node.surpriseScore * 100)}%`,
                }}
              />
            </div>
            <strong>{Math.round(node.surpriseScore * 100)}%</strong>
          </div>

          {!isRoot && (
            <div className={styles.feedbackSection}>
              <span className={styles.feedbackLabel}>这条知识连接对你有帮助吗？</span>
              <div className={styles.feedbackButtons}>
                <button
                  type="button"
                  onClick={() => onNodeFeedback("like")}
                  disabled={isNodeFeedbackPending}
                  aria-label="喜欢"
                  aria-pressed={nodeFeedback === "like"}
                  title="喜欢"
                  className={
                    nodeFeedback === "like"
                      ? styles.feedbackButtonActive
                      : styles.feedbackButton
                  }
                >
                  <span aria-hidden="true">👍</span>
                  <span>{nodeFeedback === "like" ? "已喜欢" : "喜欢"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => onNodeFeedback("dislike")}
                  disabled={isNodeFeedbackPending}
                  aria-label="不喜欢"
                  aria-pressed={nodeFeedback === "dislike"}
                  title="不喜欢"
                  className={
                    nodeFeedback === "dislike"
                      ? styles.feedbackButtonActive
                      : styles.feedbackButton
                  }
                >
                  <span aria-hidden="true">👎</span>
                  <span>{nodeFeedback === "dislike" ? "已不喜欢" : "不喜欢"}</span>
                </button>
              </div>
              {nodeFeedback && !isNodeFeedbackPending ? (
                <span className={styles.feedbackSaved} role="status">
                  已记录 · 再次点击可清除
                </span>
              ) : null}
              {nodeFeedbackError ? (
                <div className={styles.feedbackError} role="alert">
                  <span>{nodeFeedbackError}</span>
                  <button
                    type="button"
                    onClick={onRetryNodeFeedback}
                    className={styles.retryButton}
                  >
                    重试
                  </button>
                </div>
              ) : null}
            </div>
          )}
        </>
      )}

      {isRoot && (
        <p className={styles.rootHint}>
          这是本次漫游的起点。选中其他节点后可继续向外探索。
        </p>
      )}

      <div className={styles.actions}>
        {isRoot ? null : node.expanded ? (
          <button
            type="button"
            disabled
            className={`${styles.continueButton} ${styles.disabled}`}
          >
            该节点已展开
          </button>
        ) : maxNodesReached ? (
          <button
            type="button"
            disabled
            className={`${styles.continueButton} ${styles.disabled}`}
          >
            这次漫游已经长得很远了
          </button>
        ) : (
          <button
            type="button"
            onClick={onContinueWander}
            disabled={isExpanding}
            className={styles.continueButton}
          >
            <span>{isExpanding ? "正在寻找新的连接……" : "从这里继续漫游"}</span>
            {!isExpanding && <span className={styles.arrow}>→</span>}
          </button>
        )}

        {!isRoot && onDiscoverBooks && (
          <button
            type="button"
            onClick={onDiscoverBooks}
            disabled={isDiscoveringBooks}
            className={styles.discoverButton}
          >
            <span>
              {isDiscoveringBooks
                ? "正在寻找相关图书……"
                : bookError
                ? "重试相关图书"
                : books !== null
                ? "查看相关图书"
                : "发现相关图书"}
            </span>
            {!isDiscoveringBooks && <span className={styles.arrow}>→</span>}
          </button>
        )}

        {!isRoot && onBookAgent && (
          <button
            type="button"
            onClick={onBookAgent}
            disabled={isBookAgentRunning}
            className={styles.agentButton}
          >
            <span>
              {isBookAgentRunning
                ? "AI 正在决定如何检索公开图书……"
                : bookAgentError
                ? "重试 AI 选书"
                : hasBookAgentResult
                ? "查看 AI 选书"
                : "让 AI 继续选书"}
            </span>
            {!isBookAgentRunning && <span className={styles.arrow}>→</span>}
          </button>
        )}
      </div>

      {expandError ? (
        <div className={styles.error} role="alert">
          <span>{expandError}</span>
          <button
            type="button"
            onClick={onRetry}
            className={styles.retryButton}
          >
            重试
          </button>
        </div>
      ) : null}

      <LibraryWorkspace
        node={node}
        currentPath={currentPath}
        activeTab={activeBookTab}
        onTabChange={onBookTabChange}
        workspaceRef={libraryWorkspaceRef}
        onDiscoverBooks={onDiscoverBooks ?? (() => undefined)}
        isDiscoveringBooks={isDiscoveringBooks}
        books={books}
        bookError={bookError}
        onRetryBooks={onRetryBooks}
        onBookAgent={onBookAgent ?? (() => undefined)}
        isBookAgentRunning={isBookAgentRunning}
        bookAgentResult={bookAgentResult}
        bookAgentEvents={bookAgentEvents}
        bookAgentBooks={bookAgentBooks}
        bookAgentPhase={bookAgentPhase}
        bookAgentError={bookAgentError}
        onRetryBookAgent={onRetryBookAgent}
        bookFeedback={bookFeedback}
        onBookFeedback={onBookFeedback}
        isBookFeedbackPending={isBookFeedbackPending}
        bookFeedbackErrors={bookFeedbackErrors}
        onRetryBookFeedback={onRetryBookFeedback}
        bookSearchQuery={bookSearchQuery}
        onBookSearchQueryChange={onBookSearchQueryChange}
        isBookSearching={isBookSearching}
        onBookSearch={onBookSearch}
        bookSearchResults={bookSearchResults}
        bookSearchError={bookSearchError}
      />
    </div>
  );
}
