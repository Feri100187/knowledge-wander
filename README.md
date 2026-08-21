# Knowledge Wander / 知识漫游

> 一个不会只猜“你下一步想看什么”的 AI 知识探索系统。  
> 它在“相关性”与“意外性”之间主动控制知识距离，帮助用户发现那些自己原本不会主动搜索、却可能真正感兴趣的知识方向。

---

## 1. 项目背景

Knowledge Wander 是为 **大连理工大学第二届黑客松 S2** 开发的全新项目。

项目当前主攻三个展示方向：

- **开放原子赛道｜制造一点意外**
- **公开图书 API｜从知识路径到阅读线索**
- **Feedback Memory Agent｜记住偏好，同时保留未知领域**

核心问题：

传统推荐系统通常尽量预测“用户下一步最可能想看什么”，结果虽然越来越精准，却也容易把用户困在熟悉的知识范围中。

Knowledge Wander 尝试做相反的事情：

> 不只给用户最相关的答案，而是在保持一定相关性的前提下，主动制造“有意义的意外”。

**数据声明：**

比赛版本的图书信息只来自 Open Library Search API 与 Google Books API fallback。项目不保存、抓取或连接校园图书馆会话。

## Live Demo

- Frontend: https://knowledge-wander-frontend.onrender.com
- Backend Health: https://knowledge-wander-backend.onrender.com/health

### Final Delivery Overview

- **核心能力：** AI Candidate Generation、Surprise Engine、Interactive Knowledge Graph、Node Expansion、Public Book Discovery、Feedback、Memory、Lightweight Agent、Token / Latency Metrics、Candidate Cache 与 Offline Fallback；
- **Quick Start：** [Local Development / 本地启动](#local-development--本地启动)；
- **Architecture：** [docs/architecture.md](docs/architecture.md)；
- **Tracks：** OpenAtom = Meaningful Serendipity；Public Book APIs = Knowledge Path → Verified Reading Discovery；Feedback Memory Agent = Feedback → Memory → Automatic Retrieval → Personalized Exploration；
- **Demo：** [3 分钟演示脚本](docs/demo-script.md) · [60–90 秒视频脚本与 Shot List](docs/demo-video-script.md)；
- **Delivery：** Deployed / Production Re-validated；最新公开图书 API 版本已部署至 Render，并完成线上功能验证；Demo video script prepared，视频尚待人工录制。

---

例如，用户输入：

`游戏开发`

传统推荐可能继续给出：

`Unity / Unreal / C# / 图形学`

Knowledge Wander 则可能进一步带用户探索：

`心流理论 / 建筑空间设计 / 行为经济学 / 电影镜头语言 / 音乐心理学`

并解释这些领域为什么可能与“游戏开发”产生有价值的联系。

---

## 2. 项目一句话定义

**Knowledge Wander 是一个面向知识探索的 AI 系统，它不试图更精准地预测你想看什么，而是在相关性与意外性之间主动控制知识距离，带你发现那些“你不知道自己会感兴趣”的知识。**

---

## 3. 当前产品目标

用户打开网页后，可以：

1. 输入一个自己正在学习、研究或感兴趣的主题；
2. 选择“意外度”；
3. 获得若干与原主题存在联系、但知识距离不同的探索方向；
4. 查看 AI 对“为什么这两个领域有关”的解释；
5. 点击任意知识节点继续向外探索；
6. 最终形成一张不断生长的个人知识漫游地图。

最终 Features：

- AI Candidate Generation 与 Candidate Cache；
- Surprise Engine 与可控知识距离；
- Interactive Knowledge Graph 与 Node Expansion；
- Public Book Discovery（Open Library 主数据源、Google Books fallback）；
- 👍 / 👎 Feedback 与 SQLite Persistence；
- Memory Profile、Memory ON / OFF 与 Lightweight Agent；
- Token / LLM Latency / Memory Retrieval / Exploration Ratio Metrics；
- Diversity Guard 与 Offline Fallback。

---

## 4. 核心设计理念

### 4.1 不是随机推荐

本项目的目标不是简单“随机给用户一个陌生领域”。

随机推荐通常会出现两个问题：

- 太近：没有新鲜感；
- 太远：毫无意义。

Knowledge Wander 需要寻找的是：

> **有联系，但不显然。**

例如：

`Python → Java`

知识距离太近。

`Python → 古代农业灌溉制度`

知识距离太远。

而：

`Python → 编程语言 → 形式语言 → 语言学 → 人类语言结构`

属于更有意义的跨领域探索。

---

### 4.2 主动控制知识距离

系统将围绕三个基本维度评价候选知识节点：

- **Relevance / 相关性**
- **Novelty / 新颖度**
- **Cross-domain Distance / 跨领域程度**

后续形成：

`Surprise Score / 意外分数`

用户通过“意外度” Slider 控制系统倾向。

低意外度：

- 更强调相关性；
- 推荐较熟悉的相邻知识。

高意外度：

- 更强调新颖度；
- 鼓励跨学科连接；
- 但仍应保持可解释的关系。

---

## 5. 核心交互

首页核心流程：

```text
输入主题
   ↓
设置意外度
   ↓
开始漫游
   ↓
生成知识节点
   ↓
查看连接原因
   ↓
点击节点继续扩展
   ↓
知识地图不断生长
```

页面核心控件：

### Topic Input

示例：

- 游戏开发
- 人工智能
- 神经网络
- 建筑
- 摄影
- 心理学

### Surprise Level

范围：

`0 - 100`

文字：

左侧：

`安全探索`

右侧：

`疯狂漫游`

默认：

`50`

---

## 6. MVP 范围

第一阶段只完成最重要的知识探索闭环。

### P0 — 必须完成

- [ ] 输入探索主题
- [ ] 调用后端 Explore API
- [ ] AI / Mock 生成知识节点
- [ ] 显示节点名称
- [ ] 显示所属领域
- [ ] 显示节点简介
- [ ] 显示与原主题的连接原因
- [ ] 意外度 Slider
- [ ] 点击知识节点继续探索
- [ ] 知识图可视化
- [ ] 基本错误处理
- [ ] 桌面端可正常演示

### P1 — 核心完成后再做

- [ ] 公开图书探索
- [ ] 推荐书籍
- [ ] 推荐论文
- [ ] 收藏节点
- [ ] 👍 / 👎 反馈
- [ ] 探索历史
- [ ] 基础部署

### P2 — 时间充足后再做

- [ ] 用户偏好 Memory
- [ ] Feedback Memory
- [ ] 自动提取用户偏好
- [ ] 相似任务自动检索 Memory
- [ ] 七牛云赛道适配
- [ ] 轻量 Agent
- [ ] Memory token / latency 测试

### 暂不开发

除非后续明确要求，否则不要优先实现：

- 登录注册
- OAuth
- 好友系统
- 社交系统
- 管理员后台
- 大型知识图谱数据库
- Neo4j
- 自训练模型
- 本地部署大模型
- Kubernetes
- 微服务拆分

---

## 7. 图书探索赛道适配

Knowledge Wander 不应该被做成传统“图书管理系统”。

图书探索模式的目标是：

> **让用户通过知识关系重新发现原本不会主动搜索的书。**

示例：

用户输入：

`神经网络`

系统可能产生：

```text
神经网络
├─ 人工智能
├─ 神经科学
├─ 认知科学
├─ 意识哲学
└─ 复杂系统
```

用户点击：

`认知科学`

右侧可展示：

- 推荐书籍；
- 作者；
- 主题；
- 简介；
- 为什么这本书会出现在当前知识路径上。

图书探索使用统一的 `PublicBook` 模型。Open Library 先返回检索结果，结果不足时才请求 Google Books；两者都只提供公开书目元数据，不代表借阅、购买或全文访问权限。

---

## 8. 开放原子赛道适配

核心对应：

> **制造一点意外。**

本项目不是追求推荐“最准”，而是帮助用户：

- 主动走出信息茧房；
- 发现跨领域知识；
- 打开原本不知道存在的探索路径；
- 在可解释的前提下获得惊喜。

开放原子版本应重点展示：

1. 普通推荐与 Knowledge Wander 的区别；
2. 不同 Surprise Level 的结果差异；
3. “相关但不显然”的知识连接；
4. 用户点击节点后知识地图不断长大的体验。

---

## 9. 七牛云赛道后续适配思路

核心功能稳定后，可以加入反馈记忆。

例如用户行为：

```text
👍 心理学
👍 认知科学
👎 文学
👍 行为经济学
```

系统可提取：

```json
{
  "preferred_domains": [
    "psychology",
    "cognitive_science",
    "behavioral_economics"
  ],
  "disliked_domains": [
    "literature"
  ],
  "preferred_surprise_level": 0.65
}
```

下一次相似探索时：

1. 检索相关 Memory；
2. 在生成结果时体现偏好；
3. 仍保留一定未知领域比例；
4. 避免“个性化记忆”重新制造新的信息茧房。

后续需要评估：

- Memory token 成本；
- Memory 提取耗时；
- Memory 检索耗时；
- 总对话延迟；
- 偏好命中率；
- 是否准确应用用户记忆。

---

## 10. 推荐技术栈

### Frontend

- Next.js
- React
- TypeScript

### Knowledge Graph Visualization

优先考虑：

- Cytoscape.js

### Backend

- Python
- FastAPI

### Database

MVP：

- SQLite

### AI

通过统一 LLM Service 封装模型调用。

业务层禁止直接散落调用第三方模型 API。

推荐：

```text
services/
  llm_service.py
```

后续更换模型时不需要修改核心业务逻辑。

---

## 11. 推荐系统架构

```text
┌──────────────────────────────┐
│          Frontend            │
│                              │
│ Next.js / React / TypeScript │
│ Cytoscape.js                 │
└──────────────┬───────────────┘
               │ HTTP
               ↓
┌──────────────────────────────┐
│          FastAPI             │
│                              │
│ /api/explore                 │
│ /api/expand                  │
│ /api/explain                 │
│ /api/books                   │
│ /api/feedback                │
└──────────────┬───────────────┘
               │
      ┌────────┴────────┐
      ↓                 ↓
┌──────────────┐  ┌──────────────┐
│ LLM Service  │  │    SQLite    │
│              │  │              │
│ 节点生成      │  │ 收藏          │
│ 关系解释      │  │ 历史          │
│ Surprise候选 │  │ Feedback      │
└──────────────┘  └──────────────┘
```

---

## 12. 推荐仓库结构

```text
knowledge-wander/
│
├─ frontend/
│  ├─ src/
│  ├─ components/
│  │  ├─ KnowledgeGraph/
│  │  ├─ SurpriseSlider/
│  │  ├─ ExplorePanel/
│  │  └─ BookCard/
│  └─ ...
│
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  ├─ models/
│  │  ├─ services/
│  │  │  ├─ llm_service.py
│  │  │  ├─ surprise_engine.py
│  │  │  ├─ public_book_service.py
│  │  │  ├─ openlibrary_provider.py
│  │  │  ├─ google_books_provider.py
│  │  │  └─ memory_service.py
│  │  └─ prompts/
│  └─ requirements.txt
│
├─ docs/
│  ├─ architecture.md
│  ├─ demo-script.md
│  └─ third-party.md
│
├─ .env.example
├─ .gitignore
├─ README.md
└─ LICENSE
```

目录可根据实际 Next.js / FastAPI 初始化结果做合理调整，不要求为了完全匹配此树而制造无意义目录。

---

## 13. API 初步设计

### POST `/api/explore`

Request：

```json
{
  "topic": "游戏开发",
  "surprise_level": 0.5
}
```

Response：

```json
{
  "root": {
    "id": "game-development",
    "label": "游戏开发"
  },
  "nodes": [
    {
      "id": "flow-theory",
      "label": "心流理论",
      "domain": "心理学",
      "description": "研究人在高度专注状态下的心理体验。",
      "connection": "游戏难度设计与玩家心流状态存在密切关系。",
      "surprise_score": 0.62
    }
  ]
}
```

建议：

- MVP 返回至少 6 个候选节点；
- 数据结构应为后续知识图谱可视化保留 `id`；
- API schema 使用 Pydantic；
- 前后端字段命名保持稳定。

---

## 14. Milestone 开发计划

开发必须按 Milestone 推进。

原则：

> **一个 Milestone → 本地测试 → 修复 → Commit → 再进入下一阶段。**

不要一次性开发所有功能。

### Milestone 1 — 项目骨架与最小探索闭环

目标：

- Next.js 前端可运行；
- FastAPI 后端可运行；
- 前后端可通信；
- 输入主题；
- Surprise Slider；
- Mock Explore API；
- 卡片显示 6 个知识节点。

限制：

暂时不要实现：

- Cytoscape.js；
- 知识图谱；
- 真实 LLM；
- 数据库；
- 公开图书探索；
- Memory；
- Agent。

验收：

用户输入“游戏开发”，点击 Explore 后能正常看到至少 6 个 Mock 知识节点。

---

### Milestone 2 — Surprise Engine / 意外度算法

Status: Completed

已完成：

- `surprise_engine.py` 独立模块，负责 Candidate Pool、Surprise Score、Surprise Match、Ranking、过滤与 Top-K 选择；
- 每个候选知识节点拥有 `relevance`、`novelty`、`cross_domain` 三个内部维度（`0.0 ~ 1.0`）；
- `surprise_score = novelty × 0.55 + cross_domain × 0.45`，结果限制在 `0.0 ~ 1.0`；
- `surprise_match = 1 − |surprise_score − requested_surprise_level|`；
- `ranking_score = relevance × 0.50 + surprise_match × 0.50`；
- 最低相关性保护 `relevance >= 0.25`，避免返回完全无关的节点；
- 同一 Topic 在不同 Surprise Level 下返回明显不同的 Top 6（至少 3 个节点不同）；
- High Surprise 平均 `surprise_score` 显著高于 Low Surprise（差值 ≥ 0.15）；
- “游戏开发”候选池 18 个节点，覆盖 Near / Medium / Far 三层知识距离；
- Generic Fallback 候选池 14 个节点，同样具备完整的 `relevance / novelty / cross_domain` 评分；
- 结果选择采用确定性排序，相同分数按 `relevance → id` 做稳定 secondary sort；
- Backend 自动化测试覆盖：Low/High Surprise 差异、平均分差异、分数范围、非法输入 4xx、Generic Fallback；
- 前后端 API Schema 保持兼容，Frontend 无需破坏性修改；
- 真实浏览器联调通过：Slider 调整后 Explore 结果确实发生变化。

当前下一阶段：
Milestone 3 — 交互式知识地图 / Interactive Knowledge Graph

Status: Completed

已完成：

- Cytoscape.js 集成，Root + Candidate Nodes + Edges；
- 点击节点 Select 并显示 Detail Panel（Domain、Description、Connection、Surprise Score）；
- 从任意 Candidate 继续漫游：复用 `POST /api/explore`，以选中节点为 source-of-truth，避免重复 Root；
- 图谱增量 Merge：新节点/边追加到现有图谱，不覆盖；
- Expanded Node 防重复：记录 `expandedNodeIds`，已展开节点显示“该节点已展开”；
- Node / Edge 去重：添加前检查现有图谱 ID；
- 图谱规模保护：`MAX_GRAPH_NODES = 60`，达到上限后提示并禁止继续展开；
- 图谱交互：Zoom、Pan、Node Drag、Fit、自动布局（cose）；
- 新搜索 Reset Graph：清空旧图谱、节点、边、选中状态与展开记录；
- Expansion Failure 保留旧图：扩展失败时保留已有图谱，Detail Panel 显示错误并提供 Retry；
- Initial Loading 与 Expansion Loading 分离：扩展时用户仍可查看和操作已有图谱；
- `GET /api/books/search`：检索公开书目元数据；
- `POST /api/books/recommend`：根据知识节点返回相关图书；
- `POST /api/books/agent/discover` 与 `/stream`：从已验证书目中进行受约束的 AI 选书；
- 前端自动化测试通过（Lint / Build / 实际浏览器联调）；
- Backend 10 项测试继续通过。

---

### Milestone 4 — 真实 LLM / Real LLM Candidate Generation

Status: Completed

已完成：

- Provider-agnostic LLM Service，通过 OpenAI-compatible Chat Completions API 调用任意兼容模型；
- Prompt 独立管理于 `backend/app/prompts/knowledge_candidates.py`，要求模型生成 16～18 个覆盖 Near / Medium / Far 知识距离的候选；
- 每个 LLM Candidate 包含 `label / domain / description / connection / relevance / novelty / cross_domain`，由 Backend 继续计算 `surprise_score`；
- Pydantic 严格校验 `LLMCandidate` 与 `LLMCandidateResponse`；
- Surprise Level 不传入 Prompt，同一 Candidate Pool 支持不同 Slider 产生不同 Top 6；
- Candidate Cache（进程内存，TTL ≈ 15 分钟，上限 100 topics），避免重复调用 LLM；
- 失败自动退回 Milestone 1/2 的 Curated / Generic Fallback；
- Fallback 仅在 LLM 未配置、请求失败、返回候选不足时使用，正常情况以 LLM 候选为准；
- 自动化测试覆盖：LLM 成功、Malformed JSON、HTTP Error、Missing Key、Duplicate Candidate、Insufficient Candidates、Cache 行为、Candidate Source Priority、generation_source 标记；
- 原有 Backend 27 项测试继续通过；
- Frontend Lint / Build 通过；
- Knowledge Graph 回归正常。

---

### Milestone 5 — 公开图书探索

Status: Completed

已完成：

- `PublicBook` 统一模型：稳定 ID、作者、出版社、出版日期、ISBN、主题、简介、封面与来源链接；
- `OpenLibraryProvider`：调用官方 Search API，显式字段、User-Agent、限速与安全标准化；
- `GoogleBooksProvider`：按需 fallback，API key 只由 Backend 环境变量读取；
- `PublicBookSearchService`：Open Library 优先、结果不足时 fallback、ISBN/标题去重、进程内 TTL bounded cache；
- `GET /api/books/search`、`POST /api/books/recommend`：统一公开书目 API；
- Frontend 图书探索工作台：相关图书、AI 选书、图书检索三个模式只展示当前模式；
- API 与页面明确声明：书目来自公开 API，不代表借阅、购买或全文访问权限；
- 自动化测试覆盖：两个 provider、fallback、去重、缓存、错误映射、Agent 防幻觉与 SSE。

---

### Milestone 6 — Feedback

Status: Completed

已完成：

- 👍 / 👎 知识节点 Feedback（NodeDetailPanel）；
- 👍 / 👎 书籍推荐 Feedback（Book Card）；
- Anonymous Local User ID（localStorage + crypto.randomUUID，无登录体系）；
- SQLite 持久化（`backend/data/feedback.db`，已加入 `.gitignore`）；
- Feedback API：`PUT /api/feedback`、`GET /api/feedback`、`DELETE /api/feedback/{target_type}/{target_id}`；
- Unique Constraint：同一用户同一 Target 只有一个 Active Feedback；
- 支持 Like ↔ Dislike 切换、再次点击 Active 清除；
- 前端页面加载后恢复历史 Feedback Active State；
- Feedback 错误不影响 Knowledge Graph / Book Workspace；
- CORS 支持 GET / PUT / DELETE；
- 自动化测试 12 项（临时 DB、Upsert、Update、Clear、Persistence、User Isolation、Target Type、Invalid Value、Surprise Range、No Duplicate、GET、Runtime DB not committed）；
- 当前 Milestone 仅记录反馈；反馈驱动的个性化与 Memory 将在后续 Milestone 实现。

---

### Milestone 7 — Memory / Agent

Status: Completed

已完成：

- 从用户反馈提取偏好并聚合为轻量 Memory Profile；
- Memory Profile 持久化到 SQLite（`user_memory` + `feedback` 表）；
- 相似探索自动检索 Memory 并在 Prompt 中注入 `{memory_context}`；
- `{memory_context}` placeholder 直接替换，无残留、无双重插入；
- LLM Provider 返回 `usage` 时，真实记录 `prompt_tokens / completion_tokens / total_tokens`；
- Provider 未返回 `usage` 时，字段为 `null`，不做估算；
- `LLMGenerationResult` 统一携带 `candidates / cache_hit / tokens / latency_ms`；
- Candidate Cache 命中时，本次请求 `prompt_tokens = completion_tokens = total_tokens = 0`，`latency_ms = 0`；
- Surprise Level 不进入 Candidate Cache Key，仅 Topic + Memory Signature 决定缓存；
- Memory OFF 使用 `no-memory` 独立命名空间，不与 Memory ON 共享缓存；
- 前端 Memory Inspector 显示真实缓存命中状态、Token 与 LLM 耗时；
- Backend 测试覆盖：Prompt placeholder、Cache Miss/Hit、Token Metrics、Provider 无 Usage、Memory 隔离、Memory OFF 隔离。

目标：

仅当前述核心功能已经稳定时进入。

- 从用户反馈提取偏好；
- 保存轻量 Memory；
- 相似探索自动检索；
- Prompt 中使用相关 Memory；
- 记录 token 和 latency；
- 验证记忆是否真正改变结果。

---

### Milestone 8 — Demo Polish

目标：

- UI 动画；
- Loading 状态；
- 错误提示；
- Demo 数据；
- 演示路径；
- 部署；
- README 完善；
- Demo 视频。

---

## Development Progress / 开发进度

### Milestone 1 — 项目骨架与最小探索闭环

Status: Completed

主要成果：Next.js + React + TypeScript 前端、FastAPI 后端、Frontend ↔ Backend API 联调、Topic / Surprise / `POST /api/explore`、Mock Explore、至少 6 个节点、Result UI、Loading / Error Handling、环境配置与本地启动说明。

### Milestone 2 — Surprise Engine

Status: Completed

主要成果：Candidate Pool、Relevance / Novelty / Cross-domain scoring、最低相关性保护、Surprise Level 驱动 Top 6 选择。

### Milestone 3 — 交互式知识地图

Status: Completed

主要成果：Cytoscape.js Knowledge Graph、Root / Selected Node、Node Detail、Zoom / Pan / Drag、Node Expansion 与图谱规模保护。

### Milestone 4 — Real LLM

Status: Completed

主要成果：OpenAI-compatible Candidate Generation、Pydantic 校验、Candidate Cache、AI / Hybrid / Offline 来源标记与自动 Fallback。

### Milestone 5 — Public Book Discovery

Status: Completed

主要成果：Knowledge Node → Unexpected Book Discovery、3–4 本公开书目、推荐理由与来源说明。

### Milestone 6 — Feedback Persistence

Status: Completed

主要成果：知识节点与书籍 👍 / 👎 / Clear、SQLite Persistence、反馈状态恢复与友好错误处理。

### Milestone 7 — Feedback Memory Agent

Status: Completed

主要成果：Memory Profile、Memory ON / OFF、Automatic Retrieval、Memory-aware Candidate Cache、Diversity Guard、真实 Token / Cache Hit / LLM Latency / Memory Retrieval / Exploration Ratio Metrics。

### Milestone 8 — Demo Polish / Final Delivery

Status: Completed

主要成果：首屏价值表达、Topic / Surprise UX、Graph / Detail / Book Workspace / Feedback / Memory / Metrics 打磨、Loading / Error / Fallback、三档桌面响应式与 Accessibility baseline、Production URL / CORS / Health 支持、最终文档与提交清单。

当前下一阶段：

Final Review / Submission

Status: Ready

Milestone 8 是最终开发 Milestone。停止新增产品功能，不进入 Milestone 9；后续仅进行提交检查、Demo 排练、视频录制与比赛表单提交。

---

## Local Development / 本地启动

前后端需要在两个终端中分别启动。

### Backend

Windows PowerShell：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_local.py
```

如果本机策略不允许激活虚拟环境，也可以直接运行：

```powershell
.\.venv\Scripts\python.exe run_local.py
```

也可以在仓库根目录双击 `start-local.bat`，它会启动 Backend、Frontend，
等待 `http://localhost:3000` 可访问后自动打开浏览器。脚本会优先使用
`backend\.venv\Scripts\python.exe`，Backend / Frontend 窗口会独立保留以便查看日志。

启动后可访问：

- API：`http://localhost:8000/api/explore`
- Health：`http://localhost:8000/health`
- Swagger Docs：`http://localhost:8000/docs`

### Frontend

Windows PowerShell：

```powershell
cd frontend
Copy-Item ..\.env.example .env.local
npm install
npm run dev
```

打开：`http://localhost:3000`

Frontend 可选配置：

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

生产构建时将其设置为实际 Backend URL；未设置时，开发环境使用本地 Backend，生产环境使用同源 API 地址。

### Public Book APIs / 公开图书数据源

比赛版本只访问公开书目 API：

```text
Frontend → FastAPI → PublicBookSearchService
                    ├─ Open Library（主数据源）
                    └─ Google Books（结果不足时 fallback）
```

Backend 环境变量：

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

Open Library 请求使用明确的 `KnowledgeWander/1.0` User-Agent、轻量节流和 bounded TTL cache；Google Books key 如果配置，只保留在 Backend 环境中。前端不读取任何 provider secret。

公开图书路由：

```text
GET  /api/books/search?q=Python&limit=10
POST /api/books/recommend
POST /api/books/agent/discover
POST /api/books/agent/discover/stream
```

Render 部署只需要访问公开 HTTPS API，不依赖浏览器、隧道或本地会话。

---

## LLM Configuration

Knowledge Wander 通过 OpenAI-compatible Chat Completions API 接入任意 LLM Provider。

### 环境变量

在 `backend/.env` 中配置：

```text
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-provider.example.com/v1
LLM_MODEL=your-model-name
```

可选参数：

```text
LLM_TIMEOUT_SECONDS=25
LLM_TEMPERATURE=0.7
LLM_CANDIDATE_COUNT=12
LLM_MAX_TOKENS=3000
LLM_JSON_MODE=false
LLM_REASONING_EFFORT=
```

`LLM_JSON_MODE=true` 时会请求 Provider 返回 JSON object；仅在兼容该 OpenAI-compatible 参数的 Provider 上启用。
`LLM_REASONING_EFFORT` 可选，仅在当前 Provider / Model 明确支持时设置为 `low`、`medium` 或 `high`；未设置时不发送该参数。

### 说明

- `LLM_BASE_URL` 应指向 API 根路径，例如 `https://api.openai.com/v1` 或 `https://your-provider.example.com/v1`。系统会自动追加 `/chat/completions`。
- 如果未配置 `LLM_API_KEY`，Backend 仍可正常启动，并自动使用离线候选池（Curated / Generic Fallback）。
- API Key 仅保存在 Backend 环境变量中，不会暴露给 Frontend。
- 修改 `backend/.env` 后需要重启 Backend 才能生效。

---

## 15. 当前开发状态

当前状态：

**Milestone 1–8 Completed / Public Book API Migration Added**

最终交付包含：

- Real LLM Candidate Generation + Surprise Engine + Candidate Cache；
- Interactive Knowledge Graph + Node Expansion + Meaningful Connection；
- Public Book Discovery + Open Library / Google Books normalized metadata + recommendation reasons；
- Feedback + SQLite + Memory Profile + Lightweight Agent + Diversity Guard；
- Cache / Token / LLM Latency / Memory Retrieval / Exploration Ratio Metrics；
- Offline Fallback、生产环境变量、明确 CORS、`GET /health`、在线 Demo 与部署文档；
- 3 分钟 Demo Script、60–90 秒 Demo Video Script、Architecture、Third Party、Deployment 与 Submission Checklist。

已知边界：

- 公开 API 的简介、封面与预览链接由数据源决定，缺失时保持为空；
- 项目不提供购买、借阅或全文访问能力；
- 当前在线 Demo 的 Feedback / Memory 使用 SQLite；如果 Render Backend 未配置 Persistent Disk，实例重新部署、文件系统被替换或其他非持久化环境变化可能导致数据丢失；
- 当前最新公开图书 API 版本已部署至 Render，并完成线上功能验证；
- Demo video script 已准备，视频尚待人工录制。

Milestone 8 为最终开发阶段。未经新的明确指令，不进入新的产品开发 Milestone。

---

## 16. Codex 开发规则

Codex 或其他 AI Coding Agent 在修改项目时应遵守：

### Rule 1 — 严格控制开发范围

如果当前指令只要求一个 Milestone：

**只完成该 Milestone。**

不得自行进入后续阶段。

### Rule 2 — 不做无必要重构

除非：

- 当前架构明确阻碍功能；
- 存在严重技术债；
- 用户明确要求。

否则不要大规模重构已经稳定工作的代码。

### Rule 3 — 每次完成后必须测试

至少：

- Backend 启动测试；
- Frontend 启动测试；
- API 联调；
- 浏览器基本使用流程；
- Console 严重错误检查。

### Rule 4 — 不泄露密钥

不得提交：

- API Key
- Token
- Password
- Secret
- Cookie
- Private Key

使用：

`.env`

并提供：

`.env.example`

### Rule 5 — 第三方资源可追溯

如使用：

- 第三方代码；
- 开源项目；
- 模型；
- API；
- 图标；
- 图片；
- 数据集；

应记录来源，并最终整理到：

`docs/third-party.md`

### Rule 6 — 可解释

不要为了“看起来高级”引入无法解释的复杂架构。

每个核心模块需要能够向评委解释：

- 为什么存在；
- 输入是什么；
- 输出是什么；
- 如何工作。

---

## 17. Git 与提交建议

推荐每个 Milestone 完成后独立 Commit。

示例：

```text
chore: initialize knowledge wander project
feat: implement mock explore flow
feat: add surprise engine
feat: add interactive knowledge graph
feat: integrate llm exploration
feat: add public book discovery
feat: add feedback collection
feat: add feedback memory
fix: improve explore error handling
docs: prepare hackathon submission
```

不要等到项目最后一天才第一次 Commit。

---

## 18. 安全与比赛规范

项目必须保证：

- 公开仓库中不包含真实账号密码；
- 不包含 API Key；
- 不提交未经授权的个人数据；
- 不将赛前完整旧项目包装为参赛作品；
- 对第三方代码、模型、素材、API 进行记录；
- README 中保留项目运行与环境配置方法；
- 最终代码能够被复现或运行。

---

## 19. Demo 设计目标

最终 Demo 最好能够在 60–90 秒内展示项目核心价值。

推荐路径：

1. 输入 `游戏开发`；
2. Surprise Level = 20；
3. 展示相邻领域；
4. 调到 Surprise Level = 80；
5. 出现“心流理论 / 建筑 / 行为经济学”等跨领域节点；
6. 点击“心流理论”；
7. 地图向外扩展；
8. 打开某节点；
9. 展示“为什么与你有关”；
10. 切到图书探索工作台；
11. 展示一本意外发现的书；
12. 如果 Memory 已完成，再展示一次用户反馈影响下一次探索。

---

## 20. 成功标准

项目最终不是以“代码量最多”为目标。

最重要的成功标准：

> 用户真的能够因为 Knowledge Wander，遇见一个自己原本不会主动搜索的知识方向，并理解这个意外为什么有价值。

如果这个体验成立，项目核心就成立了。

---

## 21. 当前下一步

当前进入：

**Final Review / Submission / Demo Rehearsal**

Status: Ready

Milestone 8 与公开图书 API 迁移已完成代码、自动化验证和 Render 线上验证；剩余人工动作是 Demo 排练、视频录制与比赛表单提交。
