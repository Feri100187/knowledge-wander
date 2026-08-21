"use client";

import { useState } from "react";

import type { FeedbackValue } from "@/types/feedback";
import type { PublicBook } from "@/types/book";

import styles from "./NodeDetailPanel.module.css";

function valueOrFallback(value: string | null): string {
  return value || "未提供";
}

function sourceLabel(source: PublicBook["source"]): string {
  return source === "openlibrary" ? "Open Library" : "Google Books";
}

function isbnLabel(book: PublicBook): string | null {
  return book.isbn_13 || book.isbn_10;
}

export default function BookCard({
  book,
  reason,
  feedbackValue,
  isPending = false,
  error = null,
  onBookFeedback,
  onRetryBookFeedback,
}: {
  book: PublicBook;
  reason?: string;
  feedbackValue?: FeedbackValue | null;
  isPending?: boolean;
  error?: string | null;
  onBookFeedback?: (bookId: string, value: FeedbackValue) => void;
  onRetryBookFeedback?: () => void;
}) {
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false);
  const isbn = isbnLabel(book);
  const hasFeedback = Boolean(onBookFeedback);

  return (
    <article className={styles.realBookCard}>
      <div className={styles.bookCardTopline}>
        {book.cover_url ? (
          // Public providers return dynamic cover hosts, so use a plain image element.
          // eslint-disable-next-line @next/next/no-img-element
          <img className={styles.bookCover} src={book.cover_url} alt={`《${book.title}》封面`} />
        ) : (
          <div className={styles.bookCoverPlaceholder} aria-hidden="true">▧</div>
        )}
        <div className={styles.bookCardHeading}>
          <h5>{book.title}</h5>
          <p className={styles.realBookMeta}>
            {book.authors.length ? book.authors.join("、") : "作者未提供"}
          </p>
          <p className={styles.realBookMeta}>
            {valueOrFallback(book.publisher)} · {valueOrFallback(book.publication_year)}
          </p>
          <span className={styles.bookSourceBadge}>来源：{sourceLabel(book.source)}</span>
        </div>
      </div>

      {isbn ? <p className={styles.realBookMeta}>ISBN：{isbn}</p> : null}

      {book.subjects.length ? (
        <div className={styles.bookSubjectTags} aria-label="主题标签">
          {book.subjects.slice(0, 6).map((subject) => (
            <span key={subject}>{subject}</span>
          ))}
        </div>
      ) : null}

      {book.description ? (
        <>
          <p
            className={
              isDescriptionExpanded
                ? styles.realBookAbstract
                : `${styles.realBookAbstract} ${styles.realBookAbstractCollapsed}`
            }
          >
            {book.description}
          </p>
          <button
            type="button"
            className={styles.abstractToggle}
            onClick={() => setIsDescriptionExpanded((expanded) => !expanded)}
          >
            {isDescriptionExpanded ? "收起简介" : "展开简介"}
          </button>
        </>
      ) : null}

      {reason ? (
        <div className={styles.bookReasonBlock}>
          <span>为什么推荐？</span>
          <p className={styles.bookReason}>{reason}</p>
        </div>
      ) : null}

      <div className={styles.bookLinks}>
        {book.info_url ? (
          <a href={book.info_url} target="_blank" rel="noreferrer">查看书目信息</a>
        ) : null}
        {book.preview_url ? (
          <a href={book.preview_url} target="_blank" rel="noreferrer">预览</a>
        ) : null}
      </div>

      {hasFeedback ? (
        <div className={styles.bookFeedback}>
          <span className={styles.bookFeedbackLabel}>这本推荐有帮助吗？</span>
          <div className={styles.feedbackButtons}>
            <button
              type="button"
              onClick={() => onBookFeedback?.(book.id, "like")}
              disabled={isPending}
              aria-label="喜欢"
              aria-pressed={feedbackValue === "like"}
              className={feedbackValue === "like" ? styles.feedbackButtonActive : styles.feedbackButton}
            >
              <span aria-hidden="true">👍</span>
              <span>{feedbackValue === "like" ? "已喜欢" : "喜欢"}</span>
            </button>
            <button
              type="button"
              onClick={() => onBookFeedback?.(book.id, "dislike")}
              disabled={isPending}
              aria-label="不喜欢"
              aria-pressed={feedbackValue === "dislike"}
              className={feedbackValue === "dislike" ? styles.feedbackButtonActive : styles.feedbackButton}
            >
              <span aria-hidden="true">👎</span>
              <span>{feedbackValue === "dislike" ? "已不喜欢" : "不喜欢"}</span>
            </button>
          </div>
          {feedbackValue && !isPending ? (
            <span className={styles.feedbackSaved} role="status">已记录 · 再次点击可清除</span>
          ) : null}
          {error ? (
            <div className={styles.feedbackError} role="alert">
              <span>{error}</span>
              <button type="button" onClick={onRetryBookFeedback} className={styles.retryButton}>重试</button>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
