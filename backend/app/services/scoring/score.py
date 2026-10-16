from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app import llm
from app.models import Job, ScoreResult, StructuredCV
from app.services.cv.guard import cv_text

from .keywords import find_terms

log = logging.getLogger(__name__)

SYSTEM = """You compare a CV with a job advert and judge how well the CV fits, the way an applicant tracking system and a careful recruiter would.

Rules:
- score: 0 to 100 for how well the CV evidences what the advert asks for.
- matched: requirements from the advert that the CV clearly shows. Short phrases.
- missing: requirements clearly stated in the advert that the CV does NOT clearly show. One requirement per item, short phrase (max 12 words), no duplicates. Do not list anything the advert does not ask for. If a requirement is only partly shown, list it as missing.
- Judge only from the text given. Do not assume skills the CV does not state.
- rationale: two plain sentences at most."""


class LlmScore(BaseModel):
    score: float
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    rationale: str = ""


def combine(keyword: float | None, llm_score: float | None) -> float:
    if keyword is not None and llm_score is not None:
        return round(0.4 * keyword + 0.6 * llm_score, 1)
    if llm_score is not None:
        return round(llm_score, 1)
    if keyword is not None:
        return round(keyword, 1)
    return 0.0


def keyword_match(cv_full_text: str, job_text: str) -> tuple[float | None, list[str], list[str]]:
    """Returns (score or None if the job has no known keywords, matched, not found)."""
    wanted = find_terms(job_text)
    if not wanted:
        return None, [], []
    have = find_terms(cv_full_text)
    matched = sorted(wanted & have)
    absent = sorted(wanted - have)
    return round(100 * len(matched) / len(wanted), 1), matched, absent


def _clean_missing(items: list[str], cv_full_text: str) -> list[str]:
    have = find_terms(cv_full_text)
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        item = " ".join(raw.split())[:120]
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        terms = find_terms(item)
        if terms and terms <= have:
            continue  # the CV does mention every named skill in this gap
        out.append(item)
    return out


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


async def score_cv(cv: StructuredCV, job: Job) -> ScoreResult:
    cv_full = cv_text(cv)
    job_text = f"{job.title}\n{job.description}"
    kw_score, matched, absent = keyword_match(cv_full, job_text)

    llm_result: LlmScore | None = None
    try:
        llm_result = await llm.complete_json(
            SYSTEM,
            f"JOB TITLE: {job.title}\nCOMPANY: {job.company}\n\nJOB ADVERT:\n{job.description[:6000]}\n\nCV:\n{cv_full}",
            LlmScore,
            max_tokens=2000,
        )
    except Exception as err:  # noqa: BLE001
        log.warning("LLM scoring unavailable, using keyword score only: %s", err)

    if llm_result is not None:
        missing = _clean_missing(llm_result.missing, cv_full)
        llm_value = _clamp(llm_result.score)
        rationale = llm_result.rationale.strip()
        extra_matched = [m.strip() for m in llm_result.matched if m.strip()]
        matched_out = matched + [m for m in extra_matched if m.lower() not in {x.lower() for x in matched}]
    else:
        missing = [f"{t} (not found in your CV)" for t in absent]
        llm_value = None
        rationale = "AI scoring was unavailable, so this score is based on keyword matching only."
        matched_out = matched

    return ScoreResult(
        ats_score=combine(kw_score, llm_value),
        keyword_score=kw_score or 0.0,
        llm_score=llm_value or 0.0,
        matched_keywords=matched_out,
        missing_requirements=missing,
        rationale=rationale,
    )
