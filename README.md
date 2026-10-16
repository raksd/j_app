# Job Application Assistant

A local app that takes a job link you paste in, scores it against your CV, tailors the CV, writes a cover letter, and logs every application to an Excel tracker.

Everything runs on your own machine. Your CV, the generated documents and the tracker never leave it.

## What it does

1. Upload your base CV once (`.docx`). It is parsed into a structured form and saved.
2. Paste a job link. The app reads the posting. If the page is behind a login wall it asks you to paste the title, company and description instead.
3. You get an ATS score out of 100, the keywords that matched, and the requirements your CV cannot honestly claim.
4. "Prepare" produces a tailored CV and a cover letter, both as `.docx`.
5. You edit the cover letter, download the files, and apply on the employer's site yourself. The app never submits anything.
6. "Mark as applied" appends a row to `data/tracker.xlsx`. Later you update the status (Interview, Rejected, ...) from a dropdown.

The tailoring only rephrases, reorders and emphasises what is already in your CV. It never invents a skill, employer, date or qualification — a code check re-verifies this after the model has run.

## Running it

Backend:

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Frontend, in a second terminal:

```
cd frontend
npm install
npm run dev
```

The UI is at http://localhost:5173 and proxies `/api` to the backend on port 8000.

## Configuration

Copy `backend/.env.example` to `backend/.env`. By default (`LLM_BACKEND=claude_code`) the AI steps use the Claude login already on the machine through the Claude Agent SDK, so no API key is needed. Set `LLM_BACKEND=api` and `ANTHROPIC_API_KEY` to use the API instead.

`backend/.env` and the whole `data/` folder are git-ignored. They hold your keys and your personal data.

## Tests

```
cd backend
.venv\Scripts\python -m pytest -q
```

167 tests, all offline: the model and every HTTP call are faked, so no network and no API key are needed. CI runs the same suite plus the frontend type-check and build on every push.

## Layout

| Path | What's in it |
|---|---|
| `backend/app/routers/` | HTTP routes: cv, jobs, applications, files |
| `backend/app/services/manual/` | Reads a pasted job link safely and extracts the posting |
| `backend/app/services/cv/` | Parse, tailor, honesty guard, write `.docx` |
| `backend/app/services/scoring/` | Keyword match plus LLM match, combined into the ATS score |
| `backend/app/services/cover_letter/` | Generates and saves the letter |
| `backend/app/storage/` | `tracker.xlsx` and the structured CV on disk |
| `frontend/src/` | React + Vite + TypeScript UI |
| `plan.md`, `board.md` | Architecture decisions and the build board |

## Notes on safety

- Fetching a pasted link blocks private and internal addresses, re-checks on every redirect, and caps size, time and redirect count, so a crafted link cannot reach anything on your network.
- File downloads are restricted to `data/output` and reject path traversal.
- The tracker is a file you edit by hand, so reading it is forgiving: odd date formats, a score typed as `N/A`, an unrecognised status. A row that still cannot be read is skipped with a warning rather than blanking the whole page.
