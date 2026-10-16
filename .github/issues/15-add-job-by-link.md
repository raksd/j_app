# 15 Add a job by link (manual)
Labels: backend, frontend, jobs

## Description
Paste a job link (LinkedIn, Indeed, a company careers page, anything). The app reads the posting, turns it into a `Job`, scores it against your CV, and you continue the normal flow: tailored CV, cover letter, review, mark as applied.

## Flow
1. User pastes a URL on the Search page ("Add a job link").
2. Backend fetches that one page, as a normal browser visit would, and extracts title, company, location, description.
3. If the page can't be read (login wall, blocked, empty), the UI asks the user to paste the job title, company and description text instead. The URL is kept as the job link.
4. The job is scored and opens in Job Review, same as a searched job.

## Acceptance criteria
- [x] `POST /api/jobs/from-url` takes `{url, title?, company?, description?}` and returns `JobWithScore`
- [x] Extraction order: schema.org `JobPosting` JSON-LD, then OpenGraph/meta tags, then LLM extraction from the visible page text
- [x] Extraction copies only what the page says: nothing invented. Missing fields stay empty, and company/title may be asked of the user
- [x] Job `id` is a stable hash of the normalised URL (tracking params removed), `source` is the site's domain (for example `linkedin.com`), `work_mode` inferred from the text
- [x] LinkedIn/Indeed "login wall" or "sign in to view" pages and pages with too little text are detected and return HTTP 422 with a clear message asking for pasted text
- [x] If `description` is supplied, no fetch is needed; it is used as the posting text
- [x] Only http/https URLs; localhost, private and link-local addresses are rejected (no fetching internal network resources); redirects limited and re-checked; response size and timeout capped
- [x] The app does not log in to any site, use the user's cookies, or automate a browser
- [x] The same job added twice does not create duplicates in the Excel tracker (same `id` is detected when marking as applied)
- [ ] Frontend: "Add a job link" box on the Search page, with the paste-text fallback form shown when the backend returns 422; result opens Job Review (422 paste form checked in browser; the success path into Job Review not yet run)
- [x] Tests use saved sample HTML and mocked HTTP only
