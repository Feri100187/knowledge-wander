import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ProgressiveBookList from "@/components/ProgressiveBookList";

const books = [
  { id: "book-1", title: "第一本" },
  { id: "book-2", title: "第二本" },
  { id: "book-3", title: "第三本" },
];

const originalMatchMedia = window.matchMedia;

afterEach(() => {
  vi.restoreAllMocks();
  if (originalMatchMedia) {
    window.matchMedia = originalMatchMedia;
  } else {
    delete (window as Partial<Window>).matchMedia;
  }
});

describe("ProgressiveBookList", () => {
  it("starts with one card and appends the remaining cards without changing order", async () => {
    render(
      <ProgressiveBookList
        items={books}
        listKey="recommendation-1"
        getItemKey={(book) => book.id}
        className="book-list"
        renderItem={(book) => <span>{book.title}</span>}
        revealInterval={80}
      />,
    );

    await waitFor(() => expect(screen.getByText("第一本")).toBeTruthy());
    expect(screen.queryByText("第二本")).toBeNull();

    await waitFor(() => expect(screen.getByText("第二本")).toBeTruthy(), { timeout: 500 });
    await waitFor(() => expect(screen.getByText("第三本")).toBeTruthy(), { timeout: 500 });
    expect(screen.getByText("第一本").parentElement?.parentElement?.textContent).toBe(
      "第一本第二本第三本",
    );
  });

  it("shows all cards directly when reduced motion is enabled", async () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      }),
    });

    render(
      <ProgressiveBookList
        items={books}
        listKey="reduced-1"
        getItemKey={(book) => book.id}
        renderItem={(book) => <span>{book.title}</span>}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("第一本")).toBeTruthy();
      expect(screen.getByText("第二本")).toBeTruthy();
      expect(screen.getByText("第三本")).toBeTruthy();
    });
  });
});
