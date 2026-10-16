# 07 CV tailoring: human voice, no invented details
Labels: backend, cv, ai

## Description
Produce a job-specific `.docx` CV by rephrasing and reordering real content only. The result must read like a person wrote it, and must contain no detail that is not in the original CV.

## Acceptance criteria

### Natural, human language
- [ ] Summary and bullets use plain, everyday wording in a normal professional tone, as a real candidate would write
- [ ] Avoids buzzword and AI-sounding filler: "spearheaded", "leveraged", "synergy", "results-driven", "dynamic", "passionate", "proven track record", "cutting-edge", "seamlessly", "robust"
- [ ] Avoids formulaic patterns: every bullet starting with the same verb, every bullet ending in "resulting in...", em-dash heavy phrasing, lists of exactly three adjectives
- [ ] Sentence length and structure vary; bullets stay short and specific, close to the original author's own style and voice
- [ ] First person is not used in the CV (no "I"); the summary is written in a natural, direct voice
- [ ] The job's wording is borrowed only where it truthfully describes what the candidate already did; no keyword stuffing
- [ ] A language-check test flags a banned-phrase list and fails if tailored text contains any of those phrases

### No made-up details (zero tolerance)
- [ ] Guard removes any skill, tool or technology not present in the original CV text
- [ ] Guard restores experience titles, companies, locations and dates from the original; entry count and order unchanged
- [ ] Guard reverts any bullet containing a number, percentage, currency amount, team size or duration not in the original role
- [ ] No new employers, projects, certifications, degrees or achievements can be added; education and certifications are copied unchanged
- [ ] Summary may not claim years of experience, seniority, or domain expertise that the original does not support
- [ ] If the job needs something the CV lacks, it is left out of the CV and reported in `missing_requirements`, never worked in
- [ ] Contact details are copied exactly as in the original

### Output and audit
- [ ] Output `cv.docx` is a single-column ATS-friendly layout (no tables, images, text boxes)
- [ ] `changes[]` lists every edit in plain English, including anything the guard reverted and why
- [ ] Write-then-parse round trip keeps name, skills and experience
- [ ] If the LLM is unavailable or the guard rejects most of its output, the original CV is returned unchanged with a note, never a half-edited or invented version

### Tests
- [ ] Simulated LLM invents a skill, a metric, a job, a certification and a years-of-experience claim; all are blocked
- [ ] Simulated LLM returns buzzword-heavy text; the language check flags it
- [ ] Tests run offline with the LLM mocked
