# 06 ATS scoring and requirement gaps
Labels: backend, scoring

## Description
Score a CV against a job and list requirements the CV does not evidence.

## Acceptance criteria
- [ ] ATS score = round(0.4 * keyword_score + 0.6 * llm_score, 1), range 0-100
- [ ] Keyword matching has no substring false positives (java does not match javascript) and handles aliases (k8s, js, ML)
- [ ] `missing_requirements` lists only genuinely unevidenced job requirements, one per item
- [ ] If the LLM call fails, scoring degrades to the keyword score and does not raise
- [ ] Matched keywords and rationale returned for the UI
- [ ] Unit tests cover arithmetic, aliasing, degradation
