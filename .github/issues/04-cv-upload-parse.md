# 04 CV upload and parsing
Labels: backend, cv

## Description
Upload the base CV (.docx) and convert it into a `StructuredCV`.

## Acceptance criteria
- [ ] `POST /api/cv/upload` accepts .docx only and rejects other types with a clear error
- [ ] File saved to `data/cv/base.docx`; parsed result saved to `data/cv/structured.json`
- [ ] `parse_cv` extracts name, contact, summary, skills, experience (title, company, dates, bullets), education
- [ ] `parse_cv_with_llm` falls back to `parse_cv` when the LLM is unavailable
- [ ] Tables in the CV are read in document order
- [ ] `GET /api/cv` returns the CV or 404 when none uploaded
- [ ] Tests use generated .docx samples, no network
