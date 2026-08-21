"use client";

import type { RefObject } from "react";

import type { FeedbackValue } from "@/types/feedback";
import type { GraphNodeData } from "@/types/graph";
import type {
  BookAgentBook,
  BookAgentPhase,
  BookAgentResponse,
  BookAgentStreamEvent,
  BookRecommendation,
  BookSearchResponse,
  BookWorkspaceTab,
} from "@/types/book";

import AgentExecutionTimeline from "@/components/AgentExecutionTimeline";
import BookCard from "@/components/BookCard";
import BookSearchPanel from "@/components/BookSearchPanel";
import ProgressiveBookList from "@/components/ProgressiveBookList";
import styles from "./NodeDetailPanel.module.css";
import workspaceStyles from "./LibraryWorkspace.module.css";

export interface LibraryWorkspaceProps {
  node: GraphNodeData;
  currentPath: string[];
  activeTab: BookWorkspaceTab;
  onTabChange: (tab: BookWorkspaceTab) => void;
  workspaceRef: RefObject<HTMLElement | null>;
  onDiscoverBooks: () => void;
  isDiscoveringBooks: boolean;
  books: BookRecommendation[] | null;
  bookError: string | null;
  onRetryBooks: () => void;
  onBookAgent: () => void;
  isBookAgentRunning: boolean;
  bookAgentResult: BookAgentResponse | null;
  bookAgentEvents: BookAgentStreamEvent[];
  bookAgentBooks: BookAgentBook[];
  bookAgentPhase: BookAgentPhase;
  bookAgentError: string | null;
  onRetryBookAgent: () => void;
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

function LibraryWorkspace({
  node,
  currentPath,
  activeTab,
  onTabChange,
  workspaceRef,
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
}: LibraryWorkspaceProps) {
  const isRoot = node.isRoot;
  const currentTab: BookWorkspaceTab = isRoot ? "search" : activeTab;
  const displayedAgentBooks = bookAgentBooks.length
    ? bookAgentBooks
    : bookAgentResult?.books ?? [];
  const hasAgentOutput =
    isBookAgentRunning ||
    bookAgentEvents.length > 0 ||
    displayedAgentBooks.length > 0 ||
    Boolean(bookAgentResult) ||
    Boolean(bookAgentError);

  const recommendationTab = (
    <div className={styles.bookSection}>
      <div className={styles.bookSectionHeader}>
        <div className={styles.bookTitleRow}>
          <h5 className={styles.bookSectionTitle}>相关图书</h5>
          <span className={styles.realtimeBadge}>公开 API</span>
        </div>
        <p className={styles.bookSectionIntro}>
          从 Open Library 开始查找，结果不足时再使用 Google Books 补充。
        </p>
      </div>

      {isDiscoveringBooks ? (
        <div className={styles.libraryLoading} role="status" aria-live="polite">
          <span className={styles.loadingSpinner} aria-hidden="true" />
          <span className={styles.loadingText}>正在搜索图书……</span>
        </div>
      ) : bookError ? (
        <div className={styles.error} role="alert">
          <span>{bookError}</span>
          <button type="button" onClick={onRetryBooks} className={styles.retryButton}>重试</button>
        </div>
      ) : books !== null && books.length ? (
        <>
          <p className={styles.bookNotice}>结果来自公开书目元数据，可作为当前路径的阅读线索。</p>
          <ProgressiveBookList
            items={books}
            listKey={`public-recommendations-${node.id}`}
            getItemKey={(book) => book.id}
            className={styles.bookList}
            itemClassName={styles.bookReveal}
            revealInterval={150}
            renderItem={(book) => (
              <BookCard
                book={book}
                reason={book.reason}
                feedbackValue={bookFeedback[book.id] ?? null}
                isPending={Boolean(isBookFeedbackPending[book.id])}
                error={bookFeedbackErrors[book.id] ?? null}
                onBookFeedback={onBookFeedback}
                onRetryBookFeedback={() => onRetryBookFeedback(book.id)}
              />
            )}
          />
        </>
      ) : books !== null ? (
        <p className={workspaceStyles.inlineEmpty}>暂未找到与当前知识节点相关的公开图书。</p>
      ) : (
        <div className={workspaceStyles.inlineEmpty}>
          <p className={workspaceStyles.bookActionDescription}>根据当前知识节点，从公开图书数据库中寻找相关书籍。</p>
          <button type="button" onClick={onDiscoverBooks} className={workspaceStyles.primaryButton}>
            发现相关图书
          </button>
        </div>
      )}
    </div>
  );

  const agentTab = (
    <div className={styles.agentSection}>
      <div className={styles.bookTitleRow}>
        <h5 className={styles.bookSectionTitle}>AI 选书</h5>
        <span className={styles.agentBadge}>Tool Calling</span>
      </div>
      <p className={styles.bookSectionIntro}>
        AI 只能从公开图书数据库返回的真实书目中选择，不会凭记忆补写书籍事实。
      </p>
      {bookAgentError ? (
        <div className={styles.error} role="alert">
          <span>
            <strong>图书检索未完成</strong>
            <br />
            {bookAgentError}
          </span>
          <button type="button" onClick={onRetryBookAgent} className={styles.retryButton}>重试</button>
        </div>
      ) : null}
      {hasAgentOutput ? (
        <>
          <AgentExecutionTimeline
            events={bookAgentEvents}
            phase={bookAgentPhase}
            currentPath={currentPath}
            nodeLabel={node.label}
          />
          {displayedAgentBooks.length ? (
            <ProgressiveBookList
              items={displayedAgentBooks}
              listKey={`public-agent-${node.id}`}
              getItemKey={(item) => item.book.id}
              className={styles.bookList}
              itemClassName={styles.bookReveal}
              revealInterval={140}
              renderItem={(item) => (
                <BookCard
                  book={item.book}
                  reason={item.reason}
                  feedbackValue={bookFeedback[item.book.id] ?? null}
                  isPending={Boolean(isBookFeedbackPending[item.book.id])}
                  error={bookFeedbackErrors[item.book.id] ?? null}
                  onBookFeedback={onBookFeedback}
                  onRetryBookFeedback={() => onRetryBookFeedback(item.book.id)}
                />
              )}
            />
          ) : null}
        </>
      ) : (
        <div className={workspaceStyles.inlineEmpty}>
          <p className={workspaceStyles.bookActionDescription}>让 AI 分析当前知识路径，并从公开图书数据库中选择值得继续阅读的书。</p>
          <button type="button" onClick={onBookAgent} className={workspaceStyles.primaryButton}>
            让 AI 继续选书
          </button>
        </div>
      )}
      {bookAgentResult?.summary ? <p className={styles.bookNotice}>{bookAgentResult.summary}</p> : null}
    </div>
  );

  const searchTab = (
    <BookSearchPanel
      query={bookSearchQuery}
      onQueryChange={onBookSearchQueryChange}
      isSearching={isBookSearching}
      onSearch={onBookSearch}
      results={bookSearchResults}
      error={bookSearchError}
    />
  );

  const tabs: Array<{ id: BookWorkspaceTab; label: string; count: number | null }> = [
    { id: "recommendations", label: "相关图书", count: books?.length ?? null },
    { id: "agent", label: "AI 选书", count: displayedAgentBooks.length || null },
    { id: "search", label: "图书检索", count: bookSearchResults?.books.length ?? null },
  ];

  return (
    <section ref={workspaceRef} className={workspaceStyles.workspace} aria-labelledby="book-workspace-heading">
      <header className={workspaceStyles.workspaceHeader}>
        <div className={workspaceStyles.workspaceTitleRow}>
          <div className={workspaceStyles.workspaceTitle}>
            <h4 id="book-workspace-heading">图书探索</h4>
            <p>Open Library · Google Books fallback</p>
          </div>
          <span className={workspaceStyles.connectionBadge}>
            <span className={workspaceStyles.connectionDot} aria-hidden="true">●</span>
            公开 API
          </span>
        </div>
        <p className={workspaceStyles.connectionHint}>
          当前书目来自公开图书 API，不包含借阅或登录信息。
        </p>
      </header>

      {!isRoot ? (
        <div className={workspaceStyles.tabs} role="tablist" aria-label="图书探索模式">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`book-tab-${tab.id}`}
              aria-selected={currentTab === tab.id}
              aria-controls={`book-panel-${tab.id}`}
              onClick={() => onTabChange(tab.id)}
              className={currentTab === tab.id ? workspaceStyles.tabActive : workspaceStyles.tab}
            >
              <span>{tab.label}</span>
              {tab.count !== null ? <span className={workspaceStyles.tabCount}>{tab.count}</span> : null}
            </button>
          ))}
        </div>
      ) : null}

      {!isRoot ? (
        <>
          <div id="book-panel-recommendations" role="tabpanel" aria-labelledby="book-tab-recommendations" hidden={currentTab !== "recommendations"} className={currentTab === "recommendations" ? `${workspaceStyles.tabPanel} ${workspaceStyles.activePanel}` : workspaceStyles.tabPanel}>
            {recommendationTab}
          </div>
          <div id="book-panel-agent" role="tabpanel" aria-labelledby="book-tab-agent" hidden={currentTab !== "agent"} className={currentTab === "agent" ? `${workspaceStyles.tabPanel} ${workspaceStyles.activePanel}` : workspaceStyles.tabPanel}>
            {agentTab}
          </div>
          <div id="book-panel-search" role="tabpanel" aria-labelledby="book-tab-search" hidden={currentTab !== "search"} className={currentTab === "search" ? `${workspaceStyles.tabPanel} ${workspaceStyles.activePanel}` : workspaceStyles.tabPanel}>
            {searchTab}
          </div>
        </>
      ) : (
        <div className={`${workspaceStyles.tabPanel} ${workspaceStyles.activePanel}`}>
          {searchTab}
        </div>
      )}
    </section>
  );
}

export default LibraryWorkspace;
