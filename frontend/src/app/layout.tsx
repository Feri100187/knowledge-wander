import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Knowledge Wander / 知识漫游",
  description: "在相关性与意外性之间，发现你不知道自己会感兴趣的知识。",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
