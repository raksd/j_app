# J App

A local full-stack web app that reads a web page, compares its content against a personal profile, generates tailored documents, and logs the results to a spreadsheet.

## Overview

- Paste a link (or the page text) and the app extracts the key details.
- Scores how well the page content matches a stored profile.
- Produces tailored `.docx` documents with a guard against invented facts.
- Keeps a spreadsheet log with status tracking and follow-up flags.

Everything runs on your own machine; data stays in a local, git-ignored `data/` folder.

## Skills demonstrated

- **Backend:** Python, FastAPI, pydantic v2, async I/O, REST API design
- **Frontend:** React 18, TypeScript, Vite
- **LLM integration:** structured JSON output, prompt design, guardrails against hallucination, graceful fallbacks
- **Security:** SSRF-safe URL fetching, path-traversal protection on downloads, input validation
- **Data and documents:** Excel (openpyxl) and Word (python-docx) automation, tolerant parsing of hand-edited files
- **Testing and quality:** pytest (180+ offline tests with faked network and LLM), ruff linting
- **Engineering workflow:** GitHub Actions CI, feature branches and pull requests

## Tech stack

| Area | Tools |
| --- | --- |
| Backend | Python 3.11+, FastAPI, uvicorn, pydantic, httpx |
| Frontend | React, TypeScript, Vite |
| Documents | python-docx, openpyxl |
| AI | Claude via `claude-agent-sdk` (Anthropic API as fallback) |
| CI | GitHub Actions (lint, tests, frontend build) |

## Getting started

**Backend** (from `backend/`):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --port 8000
```

**Frontend** (from `frontend/`):

```
npm install
npm run dev
```

Then open http://localhost:5173.

## Configuration

Settings live in `backend/.env` (see `backend/.env.example`):

| Variable | Purpose |
| --- | --- |
| `LLM_BACKEND` | `claude_code` (local Claude login) or API-key mode |
| `ANTHROPIC_API_KEY` | Optional fallback |
| `CLAUDE_MODEL` | Model to use |
| `DATA_DIR` | Where profile, outputs and the spreadsheet are stored |

## Tests

From `backend/`:

```
python -m pytest -q
```

The suite needs no network access or API key.

## Project layout

```
backend/    FastAPI app, services, storage, tests
frontend/   React + TypeScript UI
data/       Local data (git-ignored)
```

See `plan.md` for the architecture notes.
