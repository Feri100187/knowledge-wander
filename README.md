# Knowledge Wander / 知识漫游

> 一个面向知识探索的 AI 系统：不只推荐“最相关”的内容，而是在相关性与意外性之间主动控制知识距离，帮助用户发现那些自己原本不会主动搜索、却可能真正感兴趣的方向。

Knowledge Wander 为 **大连理工大学第二届黑客松 S2** 开发，当前版本已完成并部署上线。

## Live Demo

- Frontend: https://knowledge-wander-frontend.onrender.com
- Backend Health: https://knowledge-wander-backend.onrender.com/health
- Status: **Deployed / Production Re-validated**

## 核心体验

用户输入一个主题并设置“意外度”后，系统会生成一组与原主题存在联系、但知识距离不同的探索方向，并将它们组织成可继续扩展的知识图谱。

```text
输入主题
  ↓
设置意外度
  ↓
AI 生成候选知识方向
  ↓
Surprise Engine 排序
  ↓
交互式知识图谱
  ↓
点击节点继续扩展
  ↓
发现相关图书 / AI 选书
  ↓
反馈 → Memory → 下一次个性化探索
```

例如，输入 `游戏开发` 时，系统不只会继续推荐 Unity、Unreal 或图形学，也可能带用户探索：

`心流理论 / 建筑空间设计 / 行为经济学 / 电影镜头语言 / 音乐心理学`

重点不是“随机”，而是找到：

> **有联系，但不显然。**

## 核心能力

### 1. Meaningful Serendipity / 有意义的意外

候选知识节点包含 Relevance、Novelty 与 Cross-domain Distance 等信号。Surprise Engine 根据用户设置的意外度进行排序：

- 低意外度：更强调相关性，偏向相邻知识；
- 高意外度：提高跨领域程度，同时保留可解释联系；
- Diversity Guard：避免个性化后重新形成新的信息茧房。

### 2. Interactive Knowledge Graph / 交互式知识图谱

- Cytoscape.js 可视化；
- Root / Candidate Node / Edge；
- Zoom / Pan / Drag；
- 点击节点查看领域、简介、连接原因与 Surprise Score；
- 从任意节点继续漫游；
- 图谱增量生长，并提供规模保护与错误恢复。

### 3. Public Book Discovery / 公开图书探索

图书探索不是传统图书管理系统，而是把“知识路径”继续延伸到真实书目。

当前书目数据只来自：

- **Open Library Search API**：主数据源；
- **Google Books API**：结果不足时 fallback。

中文知识概念会在**检索层**转换成英文书目查询，以提高公开英文书目的覆盖率；知识图谱、界面、Tool Trace 与 AI 推荐理由仍保持中文。真实书名、作者、出版社、ISBN 等 metadata 保持数据源原文。

图书工作台包含：

- **相关图书**：根据当前知识节点推荐；
- **AI 选书**：受约束的 Tool Calling Agent 只从已验证书目中选择；
- **图书检索**：允许直接输入中文概念搜索公开书目。

公开 API 返回的是书目元数据，不代表借阅、购买或全文访问权限。

### 4. Feedback Memory Agent

- 知识节点与图书支持 👍 / 👎；
- 匿名 Local User ID，无登录体系；
- Feedback 与 Memory Profile 使用 SQLite；
- 相似探索自动检索相关 Memory；
- Memory ON / OFF 使用独立缓存空间；
- 可查看 Memory evidence；
- 记录真实 Token、LLM Latency、Cache Hit、Memory Retrieval 与 Exploration Ratio 等指标。

### 5. Resilience / 降级与容错

- Candidate Cache；
- 公开图书结果缓存与去重；
- Open Library → Google Books fallback；
- 部分数据源失败时优先返回已有真实结果；
- Agent 重复 Tool Query 会复用已有结果，不重复请求 Provider；
- LLM 不可用时可退回 Curated / Generic Offline Fallback；
- 图书封面缺失或加载失败时使用统一占位样式。

## 系统架构

```text
┌──────────────────────────────────────┐
│              Frontend                │
│ Next.js / React / TypeScript         │
│ Cytoscape.js                         │
└──────────────────┬───────────────────┘
                   │ HTTP / SSE
                   ↓
┌──────────────────────────────────────┐
│               FastAPI                │
│ Explore / Books / Feedback / Memory  │
└─────────────┬──────────────┬─────────┘
              │              │
              ↓              ↓
     ┌────────────────┐   ┌──────────┐
     │  LLM Service   │   │  SQLite  │
     │ Candidate Gen  │   │ Feedback │
     │ Book Agent     │   │ Memory   │
     └───────┬────────┘   └──────────┘
             │
             ↓
     ┌───────────────────────────┐
     │ Public Book Search Layer  │
     │ Open Library → Google     │
     └───────────────────────────┘
```

详细架构见 [docs/architecture.md](docs/architecture.md)。

## 技术栈

| Layer | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript |
| Visualization | Cytoscape.js |
| Backend | Python, FastAPI |
| Persistence | SQLite |
| AI | OpenAI-compatible Chat Completions API |
| Book Data | Open Library, Google Books |
| Deployment | Render |

## 主要 API

```text
POST /api/explore

GET  /api/books/search
POST /api/books/recommend
POST /api/books/agent/discover
POST /api/books/agent/discover/stream

PUT    /api/feedback
GET    /api/feedback
DELETE /api/feedback/{target_type}/{target_id}

GET /health
```

## Local Development / 本地启动

### 一键启动（Windows）

仓库根目录双击：

```text
start-local.bat
```

脚本会启动 Backend 与 Frontend，并在本地页面可访问后打开浏览器。

### 手动启动 Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_local.py
```

Backend：

- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

### 手动启动 Frontend

```powershell
cd frontend
npm install
npm run dev
```

打开：`http://localhost:3000`

开发环境可设置：

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 环境变量

复制仓库根目录 `.env.example`，并按本地或部署环境填写。

LLM 最低配置：

```text
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-provider.example.com/v1
LLM_MODEL=your-model-name
```

公开图书配置：

```text
OPENLIBRARY_BASE_URL=https://openlibrary.org
OPENLIBRARY_CONTACT_EMAIL=
OPENLIBRARY_TIMEOUT_SECONDS=15

GOOGLE_BOOKS_BASE_URL=https://www.googleapis.com/books/v1
GOOGLE_BOOKS_API_KEY=
GOOGLE_BOOKS_TIMEOUT_SECONDS=15

BOOK_SEARCH_CACHE_TTL_SECONDS=600
BOOK_SEARCH_CACHE_MAX_ENTRIES=200
```

API Key 只保存在 Backend 环境变量中，不会暴露给 Frontend。

## 测试与当前状态

最终版本已完成本地与线上回归：

- Backend: **126 passed**；
- Frontend: **30 passed**；
- Lint: passed；
- Production Build: passed；
- Python compileall: passed；
- Render Backend `/health`: HTTP 200；
- Render Frontend: HTTP 200；
- 线上 smoke 已验证知识图谱、相关图书、AI 选书与图书检索主流程。

当前状态：**Final Review / Submission Ready**。

## 数据、安全与已知边界

- 比赛版本图书信息只来自 Open Library 与 Google Books 的公开书目 API；
- 项目不保存、抓取或连接校园图书馆会话；
- 不在仓库中提交 API Key、Token、Password、Cookie、Private Key 或运行时数据库；
- 图书简介、封面与预览链接由公开数据源决定，字段可能缺失；
- 当前在线 Demo 的 Feedback / Memory 使用 SQLite；如果 Render Backend 未配置 Persistent Disk，重新部署或实例文件系统变化可能导致这些运行时数据丢失。

## 项目文档

- [Architecture / 架构说明](docs/architecture.md)
- [Deployment / 部署说明](docs/deployment.md)
- [Third Party / 第三方资源](docs/third-party.md)
- [3 分钟 Demo Script](docs/demo-script.md)
- [60–90 秒 Demo Video Script](docs/demo-video-script.md)
- [Submission Checklist](docs/submission-checklist.md)

## Demo 推荐路径

```text
游戏开发
  ↓
调整 Surprise Level
  ↓
观察跨领域节点变化
  ↓
点击一个意外节点继续扩展
  ↓
查看连接原因
  ↓
打开图书探索
  ↓
相关图书 / AI 选书
  ↓
点赞一个感兴趣的节点或图书
  ↓
查看 Memory 对后续探索的影响
```

## 成功标准

Knowledge Wander 不以“推荐最准”或“代码最多”为目标。

> **如果用户真的因为一次知识漫游，遇见了一个自己原本不会主动搜索的方向，并理解这个意外为什么有价值，那么项目的核心体验就成立了。**

---

License: [MIT](LICENSE)
