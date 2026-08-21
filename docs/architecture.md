# Knowledge Wander Architecture / 架构说明

本文描述比赛提交版的实际架构：知识图谱负责发现跨领域路径，公开图书服务负责从可信公共 API 中找到可验证的阅读线索。

## 1. System Overview

```text
Browser
  │
  ▼
Next.js + React
  │  same-origin or configured HTTPS API
  ▼
FastAPI
  ├─ Exploration Agent
  │   ├─ Candidate Generation / Cache
  │   ├─ Surprise Engine
  │   ├─ Memory Rank
  │   ├─ Diversity Guard
  │   └─ Offline Fallback
  ├─ PublicBookSearchService
  │   ├─ OpenLibraryProvider (primary)
  │   └─ GoogleBooksProvider (fallback)
  └─ Feedback + Memory ── SQLite
```

Frontend 负责交互、图谱动画、Tab 工作台、渐进书卡与安全 SSE 时间线。Backend 负责候选生成、排序、记忆、公开书目标准化、缓存、错误映射与持久化。LLM key 和 Google Books key 只存在于 Backend 环境变量中。

## 2. Exploration and Graph

初次探索先立即创建 root，再等待完整候选集合；返回后节点与边按顺序渐进加入，最后只执行一次布局 settle。节点扩展复用同一条渐进 reveal 路径，保留图谱、反馈、Memory 与继续漫游能力。

```text
Topic
  → Exploration Agent
  → Candidate Pool / Cache
  → Surprise Engine + Memory Rank + Diversity Guard
  → Top 6 nodes
  → progressive graph reveal
```

## 3. Public Book Model and Sources

`PublicBook` 是所有图书功能的统一领域模型，包含：

- stable `id`、`source`、`source_id`；
- title、authors、publisher、published date / year；
- ISBN-10 / ISBN-13、subjects、description、language；
- cover、bibliographic info 与 preview URL。

模型不包含校园位置、借阅状态、馆藏复制品或账户字段。

### Open Library primary

`OpenLibraryProvider` 调用官方 Search API 的 `/search.json`，只请求明确字段，不抓取 HTML，也不为每条搜索结果追加单书请求。它构造 `KnowledgeWander/1.0` User-Agent，可选联系人来自 `OPENLIBRARY_CONTACT_EMAIL`，并使用轻量请求节流。

### Google Books fallback

`GoogleBooksProvider` 调用 `/volumes`，传递 `q`、`startIndex`、`maxResults`、`orderBy=relevance`、`printType=books` 和可选语言。`GOOGLE_BOOKS_API_KEY` 只在 Backend 配置时作为后端请求参数加入，不进入前端、日志或 SSE。

### Composite policy

`PublicBookSearchService` 先请求 Open Library：

1. Open Library 至少返回 5 条可用书目时，直接使用；
2. 少于 5 条时请求 Google Books；
3. 按 ISBN-13、ISBN-10、标准化标题 + 第一作者去重；
4. 优先保留元数据更完整的一项，并返回最多 `limit` 条。

搜索结果使用进程内 bounded TTL cache，默认 TTL 600 秒、最多 200 条；相同查询不会重复请求。Open Library 与 Google Books 均失败时返回 `BOOK_SOURCE_UNAVAILABLE`，单个来源失败时仍尽量保留另一个来源的结果。

## 4. Book API and Agent

```text
GET  /api/books/search
POST /api/books/recommend
POST /api/books/agent/discover
POST /api/books/agent/discover/stream
```

相关图书推荐使用节点 label、domain、root topic 检索，再按 title / subject / description / metadata completeness 排序。用户可见工作台包含“相关图书”“AI 选书”“图书检索”，一次只展示当前模式。

Book Agent 只暴露 `search_books(query, limit, language)`。最多两次 Tool Call；第一次已有至少 5 条合适结果时，提示要求不要为了近义词再次检索。最终 LLM 只能返回 `book_id` 与 `reason`，Backend 只接受之前 Tool Result 中出现的稳定 ID，未知 ID 会被丢弃。

SSE 只发送安全进度：`agent_started`、`path`、`tool_call`、`tool_result`、`final_selection`、`book`、`complete`、`error`。不发送 hidden reasoning、完整消息、原始 provider payload 或 secret。

## 5. Feedback and Memory

```text
Feedback (like / dislike)
        │
        ▼
SQLite feedback table
        │
        ▼
Memory Profile + Memory Signature
        │
        ├─→ Candidate Generation context
        ├─→ Memory Rank
        └─→ Diversity Guard
```

图书反馈 target 使用 `PublicBook.id`，Memory 仍按知识节点 domain 与当前路径来源工作；本次数据源迁移不改变 Memory Ranking、Feedback 或 Exploration Agent。

## 6. Errors and Render Readiness

公开书目服务使用 `BOOK_SOURCE_UNAVAILABLE`、`SEARCH_TIMEOUT`、`INVALID_RESPONSE` 与 `NO_RESULTS`。错误响应只包含安全 code / message，不包含 API key 或原始响应。Render Backend 直接访问两个公开 HTTPS API，不需要浏览器、浏览器 profile、隧道或本机状态。

## 7. Persistence and Deployment

Feedback 与 Memory 共用 SQLite，默认路径为 `backend/data/feedback.db`，可用 `FEEDBACK_DB_PATH` 覆盖。Render 没有 Persistent Disk 时，实例重启可能丢失这些状态；本次不改为云数据库。

`GET /health` 返回 `{"status":"ok"}`。生产 CORS 使用明确的 `FRONTEND_ORIGIN`，不使用通配符。
