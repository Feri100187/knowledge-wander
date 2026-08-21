# Third-Party Components / 第三方说明

本项目只使用仓库依赖与运行配置范围内的第三方组件。版本以 `frontend/package-lock.json`、`frontend/package.json` 与 `backend/requirements.txt` 为准。

## Frontend

| Component | 用途 | Source |
| --- | --- | --- |
| Next.js | App Router、构建与生产运行 | <https://nextjs.org/> |
| React / React DOM | UI 与交互状态 | <https://react.dev/> |
| Cytoscape.js | 交互式知识图谱、布局与拖拽 | <https://js.cytoscape.org/> |
| TypeScript | Frontend 类型检查 | <https://www.typescriptlang.org/> |
| ESLint / eslint-config-next | 静态检查与可访问性基线 | <https://eslint.org/> |

## Backend

| Component | 用途 | Source |
| --- | --- | --- |
| FastAPI | HTTP API、OpenAPI 与 CORS middleware | <https://fastapi.tiangolo.com/> |
| Pydantic | 请求、响应与书目 schema 校验 | <https://docs.pydantic.dev/> |
| httpx | 公开图书 API 与 LLM Provider HTTP client | <https://www.python-httpx.org/> |
| python-dotenv | Backend `.env` 环境变量加载 | <https://github.com/theskumar/python-dotenv> |
| Uvicorn | ASGI local / production server | <https://www.uvicorn.org/> |
| pytest | Backend regression tests | <https://docs.pytest.org/> |
| SQLite | Feedback 与 Memory 持久化 | <https://www.sqlite.org/> |

## Public Book APIs

- Open Library Search API：<https://openlibrary.org>
- Google Books API：<https://books.google.com>

图书元数据只来自这两个公开服务。Knowledge Wander 不保存校园会话、不抓取受限页面、不返回账户状态，也不包含书籍全文。公开 API 可能缺少简介、封面或预览链接，缺失字段会保持为空。

## LLM Provider Interface

Backend 使用 OpenAI-compatible Chat Completions API：

```text
LLM_BASE_URL + /chat/completions
```

运行时 Provider 由 `LLM_BASE_URL`、`LLM_MODEL` 与 `LLM_API_KEY` 决定，真实 key 不进入 Git。

## Assets

- 页面图形主要由 CSS 与 Cytoscape.js 渲染；
- 当前未引入外部照片、插画、音频或视频素材；
- `frontend/src/app/favicon.ico` 来自项目本身。
