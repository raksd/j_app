# 14 End-to-end verification with a real CV
Labels: integration, qa

## Acceptance criteria
- [ ] Backend test suite passes
- [ ] Frontend build and tests pass
- [ ] With real keys: upload CV -> create profile -> search -> prepare -> mark applied -> row appears in `tracker.xlsx`
- [ ] Tailored CV contains nothing absent from the original CV
- [ ] Status change in UI is reflected in Excel
- [ ] Contract drift between plan.md, models.py, routers, services and frontend types is zero
