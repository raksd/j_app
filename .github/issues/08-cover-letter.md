# 08 Cover letter: human voice, no invented details
Labels: backend, scoring, ai

## Description
Generate a one-page cover letter that explains why the applicant suits the job. It must read like a person wrote it, and must contain no detail that is not in the original CV.

## Acceptance criteria

### Natural, human language
- [ ] Plain, everyday wording in a normal professional tone, as a real candidate would write to a hiring manager
- [ ] 3-4 short paragraphs, roughly 250-320 words, tied to the company and role
- [ ] Avoids cliches and AI-sounding filler: "I am writing to apply", "passionate", "team player", "results-driven", "dynamic", "proven track record", "leverage", "spearheaded", "excited to bring", "seamlessly", "robust"
- [ ] Avoids formulaic patterns: every paragraph opening the same way, em-dash heavy phrasing, lists of exactly three adjectives, a closing that restates the whole letter
- [ ] Sentence length and structure vary; first person is natural here ("I worked on...") but not repeated at the start of every sentence
- [ ] A language-check test flags a banned-phrase list and fails if the letter contains any of those phrases

### No made-up details (zero tolerance)
- [ ] Uses only evidence from the original CV: no invented employers, titles, projects, tools, metrics, team sizes, durations or achievements
- [ ] Never claims a skill or requirement listed in `missing_requirements`
- [ ] A gap may be mentioned only honestly and briefly (for example "I haven't used X yet"), and only if it fits; never framed as experience
- [ ] Company facts are limited to what is in the job posting (name, role, stated responsibilities); no invented knowledge of the company's products, culture or news
- [ ] Years of experience, seniority and domain claims must be supported by the CV
- [ ] Numbers in the letter must appear in the CV; the guard checks this and removes or rewrites offending sentences
- [ ] Applicant name and contact details copied exactly from the CV; if the hiring manager's name is unknown the letter uses a neutral greeting, never an invented name

### Output and audit
- [ ] Saves `cover_letter.txt` and `cover_letter.docx`
- [ ] `write_cover_letter_docx` regenerates the docx after the user edits the text
- [ ] If the LLM is unavailable, no letter is produced and the user gets a clear message, never a template with invented content

### Tests
- [ ] Simulated LLM invents an employer, a metric, a skill from `missing_requirements` and a company fact; all are blocked
- [ ] Simulated LLM returns cliche-heavy text; the language check flags it
- [ ] Tests run offline with the LLM mocked
