# Hackathon Submission Checklist

此清单区分仓库已准备与仍需参赛者在外部平台完成的人工动作。

## Repository and Source

- [x] GitHub Repository Visibility 已确认为 Public
- [x] Source Code 已包含 Frontend、Backend、公开图书 API 适配与 tests
- [x] `.env.example` 只包含变量名与 placeholder
- [x] 依赖版本可由 `package-lock.json` 与 `requirements.txt` 复现
- [x] LICENSE：MIT License 已添加

## Product Documentation

- [x] README 包含项目一句话、核心能力、Quick Start、Architecture、Tracks 与 Demo 入口
- [x] `docs/architecture.md`
- [x] `docs/demo-script.md`
- [x] `docs/demo-video-script.md`
- [x] `docs/third-party.md`
- [x] `docs/deployment.md`
- [x] Data Sources 说明 Open Library 主数据源与 Google Books fallback

## Quality and Security

- [ ] Backend full test：本次迁移完成后记录实际结果
- [ ] `python -m compileall app`
- [ ] `npm run lint`
- [ ] `npm run build`
- [ ] 完成 390px 移动端与桌面 Browser Regression
- [ ] 完成 tracked secret audit
- [x] `.env`、SQLite、`.venv`、`node_modules`、`.next` 均未跟踪
- [x] Google Books key 只在 Backend 环境变量中读取
- [x] SSE 不返回 hidden reasoning、原始 provider payload 或 secret

## Deployment

- [x] Backend 支持 `0.0.0.0`、平台 `PORT` 启动命令与 `/health`
- [x] Production CORS 支持 `FRONTEND_ORIGIN`
- [x] Frontend 支持 `NEXT_PUBLIC_API_BASE_URL`
- [x] SQLite Persistent Disk 限制已记录
- [x] Render 不依赖浏览器或本地会话
- [x] 记录并验证真实 Frontend / Backend URL
  - Frontend: https://knowledge-wander-frontend.onrender.com
  - Backend: https://knowledge-wander-backend.onrender.com

## Demo and Submission

- [x] 3 分钟 Demo Script 已准备
- [x] 60–90 秒 Demo Video Script 与 Shot List 已准备
- [ ] 录制并检查 Demo Video
- [ ] 上传 Demo Video（如比赛表单要求）
- [ ] 在比赛表单粘贴 GitHub URL
- [ ] 填写赛道、团队与作品信息
- [ ] 提交前再跑一次 README 链接与公开仓库检查
