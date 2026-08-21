import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PublicBook } from "@/types/book";
import BookCard from "@/components/BookCard";

const baseBook: PublicBook = {
  id: "isbn:9780000000001",
  source: "openlibrary",
  source_id: "/works/OL1W",
  title: "示例书",
  authors: ["示例作者"],
  publisher: "示例出版社",
  published_date: "2024",
  publication_year: "2024",
  isbn_10: null,
  isbn_13: "9780000000001",
  subjects: ["示例主题"],
  description: null,
  language: "chi",
  cover_url: null,
  info_url: null,
  preview_url: null,
};

describe("BookCard cover fallback", () => {
  it("renders a loaded cover with the book-specific alt text", () => {
    render(<BookCard book={{ ...baseBook, cover_url: "https://covers.example/ok.jpg" }} />);

    const cover = screen.getByRole("img", { name: "示例书 封面" });
    expect(cover.getAttribute("src")).toBe("https://covers.example/ok.jpg");
    expect(screen.queryByRole("img", { name: "暂无封面" })).toBeNull();
  });

  it.each([null, "", "   "])('renders the placeholder without an img for cover_url=%j', (coverUrl) => {
    render(<BookCard book={{ ...baseBook, cover_url: coverUrl }} />);

    expect(screen.queryByRole("img", { name: "示例书 封面" })).toBeNull();
    expect(screen.getByRole("img", { name: "暂无封面" })).toBeTruthy();
  });

  it.each(["404 response", "network error"])("switches to the placeholder after an image %s", () => {
    render(<BookCard book={{ ...baseBook, cover_url: "https://covers.example/missing.jpg" }} />);

    const cover = screen.getByRole("img", { name: "示例书 封面" });
    fireEvent.error(cover);

    expect(screen.queryByRole("img", { name: "示例书 封面" })).toBeNull();
    expect(screen.getByRole("img", { name: "暂无封面" })).toBeTruthy();
    expect(screen.getByText("BOOK")).toBeTruthy();
  });
});
