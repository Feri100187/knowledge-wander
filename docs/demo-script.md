# 3 分钟 Demo Script

## Demo 前准备（不计时）

1. 启动 Backend 与 Frontend，确认 `GET /health` 返回 `ok`。
2. 打开首页，使用同一匿名浏览器会话。
3. 不在 20 → 80 的两次探索之间提交反馈，确保 Memory Signature 不变。
4. 若公共 API 较慢，先预热一次查询，并准备解释 Open Library fallback 与离线候选。

## 0:00–0:20｜Problem

> 推荐系统越来越懂你，却也越来越容易只给你已经熟悉的东西。Knowledge Wander 不追求“更准”，而是主动控制知识距离，在保持关联的同时制造有意义的意外。

画面：首屏“知识漫游”、一句话价值主张、Topic 与 Surprise。

## 0:20–0:50｜Surprise 20

1. 点击推荐主题“摄影史”（只填入，不自动提交）。
2. 将意外度调整为 `20`，指向提示“更贴近当前主题”。
3. 点击“开始漫游”，展示逐步长出的知识图谱。

> 模型先生成一个宽候选空间，Surprise Engine 再选择知识距离。意外度不会传给 LLM。

## 0:50–1:10｜Surprise 80 + Cache

1. 保持 Topic 为“摄影史”。
2. 将意外度改为 `80`，再次点击“开始漫游”。
3. 对比节点变化，并指向“候选缓存：命中”和“LLM Token：0”。

> 候选空间没有重新请求模型；结果变化来自 Surprise Engine，而不是重新采样。

## 1:10–1:35｜Graph + Meaningful Connection

1. 点击一个明显跨领域的节点。
2. 展示“当前路径”与“为什么它与你当前路径有关？”。
3. 点击“从这里继续漫游”，说明旧图保持、只锁当前扩展。

> 这不是随机推荐。每一步都有可解释的 meaningful connection。

## 1:35–2:05｜Public Book Discovery

1. 点击“发现相关图书”。
2. 展示“图书探索”工作台中的“相关图书”Tab、3–4 张逐步出现的 Book Card 与“为什么推荐？”。
3. 指向来源 Badge：Open Library；结果不足时说明系统会使用 Google Books 补充。

> 不是搜索一本你已经知道的书，而是沿知识路径遇见一本原本不会搜索的公开书目。所有书名、作者与 ISBN 都来自 API 返回的已验证元数据。

## 2:05–2:35｜AI 选书

1. 切换到“AI 选书”或点击节点动作“让 AI 继续选书”。
2. 展示时间线：读取路径 → 调用 `search_books` → 返回候选数量 → AI 选书完成。
3. 展示书卡逐张出现，强调 SSE 只传安全进度，不展示隐藏推理。

## 2:35–3:00｜Feedback Memory Agent

1. 对一个知识节点点击 👍。
2. 对一本书点击 👍 或 👎，形成至少 2 条证据。
3. 展示“探索记忆”，点击推荐主题“游戏开发”开始新旅程。
4. 展示“记忆已应用”与“探索保留”。

> 系统会记住用户，但 Diversity Guard 仍保留未知领域，不让记忆制造新的信息茧房。

## Backup Plan

### LLM slow

- 优先演示已缓存 Topic；
- Loading 会轮换展示真实处理阶段，不显示虚假百分比；
- 解释 Candidate Pool 与 Surprise Engine 分离。

### Public API unavailable

- 保持 Backend 运行；
- 若一个来源失败，Composite Provider 尽量使用另一个来源；
- 两个来源都不可用时展示安全错误，知识图谱、Feedback 与 Memory 仍可继续演示。

### Internet unavailable

- 使用本地 Backend + Offline Fallback 演示知识图谱；
- 图书 Tab 展示清晰的不可用状态，不伪造书目；
- Feedback / Memory 使用本地 SQLite。

### Browser state contaminated

- 需要干净反馈时，使用新的浏览器会话；
- 需要展示 Memory 时，保留同一会话并现场提交至少 2 条反馈；
- 不手动删除或修改用户的真实 `.env`。
