# 09 Prepare application and log to Excel
Labels: backend, integration

## Description
End-to-end backend flow: pasted link -> score -> prepare -> log.

## Acceptance criteria
- [x] `/api/jobs/from-url` returns the job with its ATS score; 409 with a clear message when no CV exists
- [x] `/api/jobs/prepare` writes cv.docx and cover letter into `data/output/<job_id>/`
- [x] `POST /api/applications` uses the edited cover letter text, regenerates the cover letter docx, and appends the Excel row
- [x] Excel row has date applied, company, requirements not matched, ATS score, status Applied
- [x] `PATCH /api/applications/{id}/status` updates the row
- [x] The app never submits an application to an employer
