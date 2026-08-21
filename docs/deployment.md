# Deployment / 部署说明

当前目标部署：Frontend 与 FastAPI Backend 均运行在 Render；Backend 直接访问公开图书 API。

- Frontend: https://knowledge-wander-frontend.onrender.com
- Backend: https://knowledge-wander-backend.onrender.com
- Health: https://knowledge-wander-backend.onrender.com/health
- Platform: Render

## 1. Local Setup

### Backend

```powershell
cd D:\GitHub\knowledge-wander\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_local.py
```

也可以在仓库根目录运行 `start-local.bat`，它会启动 Backend 与 Frontend。

### Frontend

```powershell
cd D:\GitHub\knowledge-wander\frontend
npm ci
npm run dev
```

打开 `http://localhost:3000`。开发环境可配置：

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 2. Environment Variables

Backend 的 `backend/.env` 或 Render Environment：

```text
LLM_API_KEY=<secret>
LLM_BASE_URL=https://provider.example.com/v1
LLM_MODEL=<model-name>
FRONTEND_ORIGIN=https://frontend.example.com
FEEDBACK_DB_PATH=/persistent/path/feedback.db

OPENLIBRARY_BASE_URL=https://openlibrary.org
OPENLIBRARY_CONTACT_EMAIL=
OPENLIBRARY_TIMEOUT_SECONDS=15
GOOGLE_BOOKS_BASE_URL=https://www.googleapis.com/books/v1
GOOGLE_BOOKS_API_KEY=
GOOGLE_BOOKS_TIMEOUT_SECONDS=15
BOOK_SEARCH_CACHE_TTL_SECONDS=600
BOOK_SEARCH_CACHE_MAX_ENTRIES=200
PORT=8000
```

联系人和 API key 不要写入 Git。Google key 只由 Backend 读取，不使用任何 `NEXT_PUBLIC_` 前缀。

Frontend 只需要：

```text
NEXT_PUBLIC_API_BASE_URL=https://backend.example.com
```

## 3. Render Web Services

### Backend

- Root Directory：`backend`
- Build Command：`pip install -r requirements.txt`
- Start Command：`python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path：`/health`
- Environment：LLM、公开图书 API、`FRONTEND_ORIGIN`、`FEEDBACK_DB_PATH`
- 可选 Persistent Disk：挂载到 `/var/data`，设置 `FEEDBACK_DB_PATH=/var/data/feedback.db`

### Frontend

- Root Directory：`frontend`
- Build Command：`npm ci && npm run build`
- Start Command：`npm run start -- --hostname 0.0.0.0 --port $PORT`
- Build Environment：`NEXT_PUBLIC_API_BASE_URL=https://<backend-service>`

创建 Frontend URL 后，把它写入 Backend 的 `FRONTEND_ORIGIN` 并重新部署 Backend。

## 4. Public Book Data Sources

Backend 路由：

```text
GET  /api/books/search?q=Python&limit=10
POST /api/books/recommend
POST /api/books/agent/discover
POST /api/books/agent/discover/stream
```

Open Library 是主数据源，结果不足时才访问 Google Books。两者都失败时返回安全的 `BOOK_SOURCE_UNAVAILABLE`；单个来源失败时尽量保留另一个来源的结果。应用使用 600 秒、最多 200 条的进程内缓存，适合低频人工演示，不做压力测试。

## 5. SQLite Limitation

Feedback / Memory 使用 SQLite。Render 未配置 Persistent Disk 时，实例重启、替换或非持久化环境变化可能导致状态丢失。正式长期运行时挂载 Persistent Disk，并把 `FEEDBACK_DB_PATH` 指向挂载路径；本次不迁移数据库。

## 6. Verification

1. `GET /health` 返回 `200` 和 `{"status":"ok"}`；
2. 打开 Frontend，完成 Topic → Explore；
3. 在“相关图书”或“图书检索”中观察公开书目来源；
4. 运行“AI 选书”，确认 timeline 只显示安全进度事件；
5. Browser Console 无 CORS 或 Runtime Error；
6. 如果没有配置 Google key，确认 Open Library 结果仍能正常展示。
