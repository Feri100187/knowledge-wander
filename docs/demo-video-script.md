# 60–90 秒 Demo Video Script

目标时长：约 85 秒。建议录制 `1920×1080`，浏览器缩放 100%，只保留产品窗口。

## Narration + Timing

### 0–10s｜Problem

画面：首屏“知识漫游”。

旁白：

> 推荐越来越精准，也越来越容易只给你熟悉的答案。Knowledge Wander 主动控制知识距离，制造有意义的意外。

### 10–25s｜Surprise

画面：输入“摄影史”，Surprise 从 20 调到 80，快速对比节点。

旁白：

> LLM 只负责生成候选空间，Surprise Engine 决定最终知识距离。改变意外度不需要重新请求模型。

屏幕重点：Cache Hit、LLM Token 0。

### 25–45s｜Graph

画面：点击跨领域节点，显示选中 glow、当前路径与 connection；点击继续漫游，看图谱生长。

旁白：

> 每个节点都解释为什么与你当前路径有关，所以它不是随机推荐。

### 45–60s｜Public Books

画面：进入“图书探索”，展示 2–3 张逐步出现的 Book Card。

旁白：

> 沿知识路径遇见一本原本不会搜索的书，而不是搜索一本已经知道的书。

屏幕重点：为什么推荐、Open Library 来源、公开书目说明。

### 60–75s｜Feedback Memory

画面：节点 👍、书籍 👎、Memory Inspector 出现；切换到“游戏开发”。

旁白：

> 反馈形成轻量记忆，下一次探索自动检索；Diversity Guard 同时保留未知领域。

### 75–85s｜Closing

画面：Graph + Metrics 全景。

旁白：

> 有意义的意外、沿知识关系重新发现书，以及不会制造信息茧房的 Feedback Memory Agent。这就是 Knowledge Wander。

## Shot List

| Shot | 时长 | 画面 | 操作重点 |
| --- | ---: | --- | --- |
| 1 | 0–10s | First Screen | 中文产品名、价值主张、Topic / Surprise |
| 2 | 10–17s | Surprise 20 | 近距离提示与第一组 6 Nodes |
| 3 | 17–25s | Surprise 80 | 节点变化、Cache Hit、Token 0 |
| 4 | 25–35s | Selected Node | 当前路径、connection、意外度 |
| 5 | 35–45s | Expand | Graph 保持并生长 |
| 6 | 45–60s | Public Books | 图书探索、Book reason、来源 |
| 7 | 60–70s | Feedback | Active 文本、已记录状态 |
| 8 | 70–78s | Memory | 2+ Evidence、偏好领域、偏好意外度 |
| 9 | 78–85s | Final Wide Shot | Graph 主视觉 + Metrics + 三赛道总结 |

## Recording Notes

- 不录制 `.env`、终端环境变量、API Key 或数据库路径；
- 避免展示 Provider 控制台或个人账号；
- Provider 较慢时使用已缓存 Topic 或离线 Fallback；
- 保留鼠标移动节奏，避免频繁快速滚动；
- 录制完成后再添加字幕，本文件仅表示脚本已准备，不表示视频已录制。
