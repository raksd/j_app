# 10 Secure file download
Labels: backend, security

## Acceptance criteria
- [ ] `GET /api/files/{job_id}/{filename}` serves only files inside `data/output`
- [ ] `..`, absolute paths, encoded traversal and backslash tricks are rejected
- [ ] Unknown file returns 404
- [ ] Tests cover traversal attempts
