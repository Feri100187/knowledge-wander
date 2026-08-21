"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import type { BookSearchResponse, PublicBook } from "@/types/book";

import BookCard from "@/components/BookCard";
import ProgressiveBookList from "@/components/ProgressiveBookList";
import styles from "./NodeDetailPanel.module.css";

export interface BookSearchPanelProps {
  query: string;
  onQueryChange: (value: string) => void;
  isSearching: boolean;
  onSearch: () => void;
  results: BookSearchResponse | null;
  error: string | null;
}

export default function BookSearchPanel({
  query,
  onQueryChange,
  isSearching,
  onSearch,
  results,
  error,
}: BookSearchPanelProps) {
  const [submittedQuery, setSubmittedQuery] = useState("");

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmittedQuery(query.trim());
    onSearch();
  };

  return (
    <section className={styles.bookSearchSection} aria-label="公开图书检索">
      <form className={styles.bookSearchForm} onSubmit={submitSearch}>
        <label htmlFor="public-book-query">检索公开图书</label>
        <div className={styles.bookSearchRow}>
          <input
            id="public-book-query"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="例如：Python、machine learning"
            maxLength={100}
            disabled={isSearching}
          />
          <button type="submit" disabled={isSearching || !query.trim()}>
            {isSearching ? "检索中……" : "搜索"}
          </button>
        </div>
      </form>

      {error ? <div className={styles.bookError} role="alert">{error}</div> : null}

      {results ? (
        <div className={styles.realResults} aria-live="polite">
          <div className={styles.realResultsHeader}>
            <span>公开图书结果</span>
            <strong>{results.books.length} 条</strong>
          </div>
          {results.error_code === "NO_RESULTS" || !results.books.length ? (
            <p className={styles.noResults}>{results.message ?? "暂未找到匹配的公开图书。"}</p>
          ) : (
            <ProgressiveBookList
              items={results.books}
              listKey={`public-book-search-${submittedQuery || results.query}-${results.page}`}
              getItemKey={(book: PublicBook) => book.id}
              className={styles.realBookList}
              itemClassName={styles.bookReveal}
              revealInterval={150}
              renderItem={(book) => <BookCard book={book} />}
            />
          )}
        </div>
      ) : null}
    </section>
  );
}
