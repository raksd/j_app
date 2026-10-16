from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app import llm
from app.models import CoverLetter, Job, ScoreResult, StructuredCV
from app.services.cv import guard
from app.services.cv.language import find_letter_banned
from app.services.scoring.keywords import find_terms

from .writer import write_cover_letter_docx

log = logging.getLogger(__name__)

GREETING = "Dear Hiring Manager,"
SIGN_OFF = "Kind regards,"
MIN_WORDS = 120

SYSTEM = """You write a cover letter for a real person applying for one job. You may only use facts that are in their CV. You must never add anything.

Hard rules:
- Do not invent or imply any employer, job title, project, tool, technology, qualification, number, percentage, amount, team size, duration, achievement or years of experience that is not in the CV.
- Never claim a skill or requirement from the "not shown in the CV" list. You may mention one gap honestly and briefly (for example "I haven't worked on X directly yet"), only if it fits naturally. Never present a gap as experience.
- About the company, say only what the job advert says (its name, the role, the responsibilities it lists). Do not add knowledge of its products, culture, values or news.
- Do not write a greeting, a sign-off or the applicant's name. They are added separately.

Voice:
- 3 or 4 short paragraphs, about 250 to 320 words in total, specific to this role.
- Plain everyday wording, the way a normal professional writes to a hiring manager. First person is natural ("I worked on...") but do not start every sentence with "I".
- Vary sentence length. Do not open every paragraph the same way. Avoid em-dashes. Do not list exactly three adjectives. Do not end by restating the whole letter.
- Avoid these: "I am writing to apply", passionate, team player, results-driven, dynamic, proven track record, leverage, spearheaded, excited to bring, seamlessly, robust, utilise."""


class LetterOutput(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)


class CoverLetterError(Exception):
    """The letter could not be produced safely. No template letter is ever substituted."""


EXPERIENCE_CLAIM = re.compile(
    r"\b(I (have|had|ve|worked|built|used|led|developed|applied|delivered|managed|designed|created|ran|wrote)|"
    r"I've|my (experience|work|background)|experience (in|with|of))\b",
    re.IGNORECASE,
)
NEGATION = re.compile(
    r"\b(haven't|have not|hasn't|not yet|no experience|never|limited|don't|do not|without|yet to|new to|"
    r"not used|not worked|not directly)\b",
    re.IGNORECASE,
)


def _sentences(paragraph: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", paragraph.strip()) if s]


def _compact_cv(cv: StructuredCV) -> str:
    return json.dumps(
        {
            "summary": cv.summary,
            "skills": cv.skills,
            "experience": [
                {"title": r.title, "company": r.company, "start": r.start, "end": r.end, "bullets": r.bullets}
                for r in cv.experience
            ],
            "education": [f"{e.qualification}, {e.institution}" for e in cv.education],
            "projects": [{"name": p.name, "description": p.description} for p in cv.projects],
            "certifications": cv.certifications,
        },
        ensure_ascii=False,
    )


def _prompt(cv: StructuredCV, job: Job, score: ScoreResult, feedback: str = "") -> str:
    text = (
        f"JOB TITLE: {job.title}\nCOMPANY: {job.company}\nLOCATION: {job.location or 'not stated'}\n\n"
        f"JOB ADVERT:\n{job.description[:6000]}\n\n"
        f"NOT SHOWN IN THE CV (do not claim these): {'; '.join(score.missing_requirements) or 'none listed'}\n"
        f"CLEARLY SHOWN IN THE CV: {'; '.join(score.matched_keywords) or 'not listed'}\n\n"
        f"CV (JSON):\n{_compact_cv(cv)}\n\n"
        'Return JSON: {"paragraphs": ["...", "..."]} with the body paragraphs only.'
    )
    if feedback:
        text += f"\n\nYour previous letter had these problems. Fix them and return the full JSON again:\n{feedback}"
    return text


class _Checker:
    def __init__(self, cv: StructuredCV, job: Job, score: ScoreResult):
        self.cv_full = guard.cv_text(cv)
        posting = f"{job.title} {job.company} {job.location}"
        self.allowed = f"{self.cv_full}\n{posting}\nI I'm I've I'd I'll I’m I’ve I’d I’ll"
        cv_terms = find_terms(self.cv_full)
        wanted = find_terms(f"{job.title}\n{job.description}") | find_terms(" ".join(score.missing_requirements))
        self.unevidenced = wanted - cv_terms
        self.cv_words = guard._words(self.allowed)

    def sentence_problem(self, sentence: str) -> str | None:
        nums = guard.unsupported_numbers(sentence, self.cv_full)
        if nums:
            return f"number not in your CV ({', '.join(nums)})"
        terms = guard.novel_terms(sentence, self.allowed)
        if terms:
            return f"name or term not in your CV or the advert ({', '.join(terms)})"
        claims = [w for w in guard._words(sentence) if w in guard.SENIORITY and w not in self.cv_words]
        if claims:
            return f"seniority claim not in your CV ({', '.join(claims)})"
        banned = find_letter_banned(sentence)
        if banned:
            return f"cliche or buzzword wording ({', '.join(sorted(set(banned)))})"
        mentioned = sorted(find_terms(sentence) & self.unevidenced)
        if mentioned and EXPERIENCE_CLAIM.search(sentence) and not NEGATION.search(sentence):
            return f"claims experience in something your CV does not show ({', '.join(mentioned)})"
        return None

    def review(self, paragraphs: list[str]) -> tuple[list[str], list[str], list[str]]:
        """Returns (paragraphs with offending sentences removed, sentence problems, style problems)."""
        kept: list[str] = []
        problems: list[str] = []
        for para in paragraphs:
            good = []
            for sentence in _sentences(para):
                problem = self.sentence_problem(sentence)
                if problem:
                    problems.append(f'"{sentence[:90]}": {problem}')
                else:
                    good.append(sentence)
            if good:
                kept.append(" ".join(good))
        return kept, problems, style_problems(paragraphs)


def style_problems(paragraphs: list[str]) -> list[str]:
    out: list[str] = []
    text = "\n".join(paragraphs)
    words = len(text.split())
    if words < 200 or words > 380:
        out.append(f"length is {words} words; aim for about 250 to 320")
    openers = [p.split()[0].lower() for p in paragraphs if p.split()]
    if len(openers) >= 3 and len(set(openers)) < len(openers) - 1:
        out.append("several paragraphs open with the same word")
    if text.count("—") > 1:
        out.append("too many em-dashes")
    sentences = [s for p in paragraphs for s in _sentences(p)]
    if sentences and sum(s.startswith("I ") for s in sentences) / len(sentences) > 0.4:
        out.append('too many sentences start with "I"')
    return out


def _assemble(paragraphs: list[str], cv: StructuredCV) -> str:
    return "\n\n".join([GREETING, *paragraphs, f"{SIGN_OFF}\n{cv.full_name}"])


def save_cover_letter(text: str, cv: StructuredCV, out_dir: Path) -> CoverLetter:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cover_letter.txt").write_text(text, encoding="utf-8")
    docx_path = write_cover_letter_docx(text, cv, out_dir / "cover_letter.docx")
    return CoverLetter(text=text, docx_path=str(docx_path))


async def write_cover_letter(cv: StructuredCV, job: Job, score: ScoreResult, out_dir: Path) -> CoverLetter:
    checker = _Checker(cv, job, score)
    try:
        out = await llm.complete_json(SYSTEM, _prompt(cv, job, score), LetterOutput, max_tokens=2500)
        paragraphs, problems, style = checker.review(out.paragraphs)
        if problems or style:
            feedback = "\n".join(f"- {p}" for p in [*problems, *style])
            out = await llm.complete_json(SYSTEM, _prompt(cv, job, score, feedback), LetterOutput, max_tokens=2500)
            paragraphs, problems, style = checker.review(out.paragraphs)
    except Exception as err:  # noqa: BLE001
        raise CoverLetterError(
            f"No cover letter was written because the AI step was unavailable ({err}). Try again later."
        ) from err

    for p in problems:
        log.info("cover letter sentence removed: %s", p)
    if len(" ".join(paragraphs).split()) < MIN_WORDS:
        raise CoverLetterError(
            "No cover letter was written: the AI draft kept adding details that are not in your CV, "
            "and too little was left after removing them. Try again."
        )
    return save_cover_letter(_assemble(paragraphs, cv), cv, out_dir)
