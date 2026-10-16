# 01 Project setup and configuration
Labels: backend, setup

## Description
Runnable FastAPI project with config loaded from `.env`, a data directory, and the `/api/health` route.

## Acceptance criteria
- [x] `pip install -r backend/requirements.txt` succeeds
- [x] `uvicorn app.main:app` starts and `GET /api/health` returns `{"ok": true}`
- [x] `.env.example` lists LLM_BACKEND, ANTHROPIC_API_KEY, CLAUDE_MODEL, DATA_DIR
- [x] Data subfolders (`cv`, `output`) are created on startup
- [x] CORS allows http://localhost:5173
