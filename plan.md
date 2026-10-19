# Job Application Assistant: Architecture Plan

Local app that takes a job link you paste in, scores it against your CV, tailors the CV, writes a cover letter, and logs every application to an Excel tracker.

## 1. Decisions and reasoning

| Decision | Choice | Why |
|---|---|---|
| Backend | Python 3.11+ / FastAPI | Best ecosystem for `.docx` (python-docx), Excel (openpyxl), HTTP (httpx), Claude SDK. |
| Frontend | React + Vite + TypeScript | Standard SPA; talks to backend through `/api`; Vite dev proxy avoids CORS. |
| Runtime | Local on the user's PC | CV and personal data stay private; no auth/hosting needed. |
| Finding jobs | The user pastes a job link; the app reads that page | Scraping LinkedIn/Indeed breaks ToS and gets blocked. Job-board APIs were tried and dropped: poor match quality for the roles targeted, and cost. Pasting a link is the one method that is both legal and accurate. |
| Reading a pasted link | `services/manual/safe_fetch.py`, then a paste-the-text fallback | Many boards sit behind a login wall. When the page cannot be read, the UI asks for the title, company and description instead of failing. |
| AI | Default: the Claude login already on the laptop, via `claude-agent-sdk` (`LLM_BACKEND=claude_code`). Fallback: Claude API key (`anthropic` SDK). Model from env `CLAUDE_MODEL` | Runs on the user's existing Claude usage, no separate API key. One wrapper (`llm.py`) hides the backend. If the login hits its usage limit, calls fail with a clear error, or use the API key if one is set. At most 2 calls run at once. |
| CV format | `.docx` in, `.docx` out | Most common; editable by the user afterwards. |
| CV honesty | Rephrase, reorder and emphasise only. Never invent skills, employers, dates, or degrees | Fabrication is unethical and gets candidates rejected at background checks. Gaps are reported, not hidden. |
| ATS score | Own score: 40% deterministic keyword match + 60% LLM match | No public ATS API exists. Keyword part is repeatable and explainable; LLM part captures seniority and context. |
| Submitting | App never submits. Human reviews, then applies manually | Avoids ToS/captcha problems and keeps the user in control. |
| Record keeping | Local `.xlsx` is the system of record for applications | The user asked for Excel. They can also open and edit it directly. |
| Outcome tracking | Manual status dropdown in UI, written through to Excel | Email parsing adds large scope and permissions for little gain. |

## 2. Workflow

1. Upload the base CV once -> parsed into `StructuredCV` and saved.
2. Paste a job link -> backend reads the page, or asks you to paste the text if the page is behind a login wall.
3. See the ATS score, matched keywords, and requirements not matched in the CV.
4. "Prepare" -> backend produces a tailored CV `.docx` and a cover letter `.docx` plus text.
5. User edits the cover letter text, downloads files, applies on the employer site themselves.
6. "Mark as applied" -> one row is appended to the Excel tracker.
7. Later the user updates Status (Interview / Rejected / ...) from a dropdown.

## 3. Repository layout

```
job_app/
  plan.md
  board.md
  .github/
    issues/                            acceptance criteria per feature
    workflows/ci.yml                   runs backend tests + frontend build on every push
  backend/
    requirements.txt
    .env.example
    app/
      __init__.py
      main.py                          FastAPI app, CORS, router mounting
      config.py                        paths, env, settings
      models.py                        shared pydantic models
      llm.py                           Claude wrapper (claude_code login or API key)
      storage/
        excel_store.py                 tracker.xlsx read/write
        json_store.py                  structured CV persistence
      routers/
        cv.py jobs.py applications.py files.py
      services/
        manual/                        read a pasted job link safely, extract the posting
        cv/                            parse, tailor, honesty guard, write docx
        scoring/                       keyword + LLM ATS score
        cover_letter/                  generate and write the letter
    tests/                             167 tests, all offline (LLM and HTTP faked)
  frontend/                            Vite React TS app
  data/                                runtime data, git-ignored
    cv/base.docx  cv/structured.json
    tracker.xlsx
    output/<job_id>/cv.docx cover_letter.docx cover_letter.txt
```

## 4. Shared data models

Authoritative definitions live in `backend/app/models.py`. Summary:

- `Job`: id (stable hash of url), source, title, company, location, work_mode, description, url, posted_date, salary
- `StructuredCV`: full_name, email, phone, location, links[], summary, skills[], experience[], education[], certifications[], projects[]
- `ScoreResult`: ats_score (0-100), keyword_score, llm_score, matched_keywords[], missing_requirements[], rationale
- `TailoredCV`: cv (StructuredCV), docx_path, changes[] (human-readable list of what was changed)
- `CoverLetter`: text, docx_path
- `PreparedApplication`: job, score, tailored_cv, cover_letter
- `ApplicationRecord`: one Excel row; `ApplicationStatus` enum (`Applied|Interview|Offer|Rejected|No Response|Withdrawn`)

## 5. Service contracts (what each module exposes)

```python
# services/manual/__init__.py
def normalise_url(raw: str) -> str                               # validate and clean a pasted link
def fetch_page(url: str) -> str                                  # SSRF-safe GET, HTML only, size/time capped
def extract_job(html: str, url: str) -> Job                      # title/company/description from the page

# services/cv/__init__.py
def parse_cv(docx_path: Path) -> StructuredCV
async def parse_cv_with_llm(docx_path: Path) -> StructuredCV     # raw text -> StructuredCV via llm.complete_json
async def tailor_cv(cv: StructuredCV, job: Job, score: ScoreResult, out_dir: Path) -> TailoredCV
def write_cv_docx(cv: StructuredCV, out_path: Path) -> Path

# services/scoring/__init__.py
async def score_job(cv: StructuredCV, job: Job) -> ScoreResult
def keyword_score(cv: StructuredCV, job: Job) -> tuple[float, list[str], list[str]]  # score, matched, missing

# services/cover_letter/__init__.py
async def generate_cover_letter(cv: StructuredCV, job: Job, score: ScoreResult, out_dir: Path) -> CoverLetter
def save_cover_letter(text: str, cv: StructuredCV, out_dir: Path) -> Path
```

Tailoring rules (enforced in the prompt and re-checked in code):
1. Output must contain no skill, employer, title, date, or qualification absent from the input CV.
2. Allowed: reword bullets, reorder sections/bullets, rewrite the summary, surface existing skills that match the job.
3. `changes[]` lists every edit so the user can audit it.
4. `missing_requirements` come from the job, not the CV. They are what the CV cannot honestly claim.

## 6. HTTP API

All routes under `/api`. JSON in, JSON out, except uploads and downloads.

| Method | Route | Body | Returns |
|---|---|---|---|
| POST | `/cv/upload` | multipart `file` (.docx) | `StructuredCV` |
| GET | `/cv` | | `StructuredCV` or 404 |
| POST | `/jobs/from-url` | `{url, title?, company?, description?}` | `JobWithScore`; 422 = page unreadable (login wall), UI asks user to paste title/company/description; 400 = invalid or blocked URL |
| POST | `/jobs/prepare` | `{job: Job}` | `PreparedApplication` |
| POST | `/applications` | `{prepared: PreparedApplication, cover_letter_text: string}` | `ApplicationRecord` |
| GET | `/applications` | | `ApplicationRecord[]`; each row has `follow_up_due` (true when status is Applied and 7+ days have passed since applied) |
| PATCH | `/applications/{id}/status` | `{status, notes?}` | `ApplicationRecord` |
| GET | `/files/{job_id}/{filename}` | | file download (only inside `data/output`) |
| GET | `/health` | | `{ok: true}` |

`GET /files` must reject path traversal.

Tracker error codes: 409 duplicate id, 422 a row in the tracker cannot be read, 423 the workbook is open in Excel, 404 unknown id.

## 7. Excel tracker schema (`data/tracker.xlsx`, sheet `Applications`)

| Col | Header | Notes |
|---|---|---|
| A | ID | uuid, used by PATCH |
| B | Date Applied | ISO date |
| C | Company | |
| D | Job Title | |
| E | Location | |
| F | Work Mode | remote/hybrid/onsite |
| G | Job URL | hyperlink |
| H | ATS Score | 0-100 |
| I | Requirements Not Matched in CV | `; `-joined |
| J | CV File | path relative to `data/` |
| K | Cover Letter File | path relative to `data/` |
| L | Status | data-validation dropdown from `ApplicationStatus` |
| M | Notes | |
| N | Last Updated | ISO datetime |

Excel is written with openpyxl: header row frozen, filters on, column widths set, status validation applied. Writes are atomic (temp file then replace) and fail with a clear error if the file is open and locked in Excel.

The tracker is a file the user edits by hand, so reading it is deliberately forgiving. Dates are accepted in several written forms as well as Excel's own number format; a score typed as `72.5%` or `N/A` is read or defaulted rather than rejected; an unrecognised Status or Work Mode falls back to `Applied` / `unknown`. A row that still cannot be read is skipped with a warning in the log so the remaining rows keep loading. Status validation is re-applied on every write, so trackers created before that rule existed pick it up.

## 8. Configuration

`backend/.env` (see `.env.example`): `LLM_BACKEND` (`claude_code` or `api`), `ANTHROPIC_API_KEY` (only for `api`), `CLAUDE_MODEL` (default `claude-sonnet-5`), `DATA_DIR` (default `../data`).

## 9. How it was built

Five areas were built concurrently against the contracts above, then integrated: backend (app, routers, Excel/JSON stores, config), manual job intake, cv, scoring and cover letter, frontend. Integration was a pass to run the backend, the service tests and the frontend build, fix contract drift, then an end-to-end run with a real CV.

Tests are offline: the LLM and all HTTP calls are faked, so `pytest` runs with no network and no API key. CI (`.github/workflows/ci.yml`) runs the same tests plus the frontend type-check and build on every push.

## 10. Risks and open items

- CV parsing quality depends on CV structure. The LLM pass is the fallback for messy layouts.
- Work mode (hybrid/onsite) is often missing from a posting, so it is inferred from the description and flagged as "unknown" when unclear.
- Some job boards sit behind a login wall and cannot be read. The UI falls back to asking the user to paste the posting text.
- Excel file locking on Windows when the user has the workbook open.
- A tracker row that cannot be read is skipped silently from the user's point of view: the warning only goes to the backend log, not the UI.
