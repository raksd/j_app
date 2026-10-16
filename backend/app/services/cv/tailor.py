from __future__ import annotations

import json
from pathlib import Path

from app import llm
from app.models import Job, ScoreResult, StructuredCV, TailoredCV
from app.services.naming import document_name

from . import guard
from .guard import TailorOutput
from .language import shared_openers
from .writer import write_cv_docx

SYSTEM = """You edit a real person's CV for one specific job. You may only reword, reorder and emphasise what is already in the CV. You must never add anything.

Hard rules:
- Do not add any skill, tool, technology, employer, job title, date, qualification, certification, project, number, percentage, amount, team size or duration that is not already in the CV.
- Do not claim years of experience or seniority beyond what the CV already says.
- If the job asks for something the CV does not show, leave it out. Do not hint at it.

Voice:
- Plain everyday words, the way a normal professional writes about their own work. Keep each bullet close to the original author's own style and length.
- No buzzwords or filler: spearheaded, leveraged, utilised, synergy, results-driven, dynamic, passionate, proven track record, cutting-edge, seamless, robust, streamline, holistic.
- No first person ("I", "my"). No em-dash phrasing. Do not end every bullet with "resulting in ...". Do not start every bullet with the same verb. Vary sentence length.
- Borrow the job's wording only where it truthfully describes what the person already did. No keyword stuffing."""


def _compact(cv: StructuredCV) -> dict:
    return {
        "summary": cv.summary,
        "skills": cv.skills,
        "experience": [
            {
                "index": i,
                "title": r.title,
                "company": r.company,
                "bullets": [{"source": j, "text": b} for j, b in enumerate(r.bullets)],
            }
            for i, r in enumerate(cv.experience)
        ],
    }


def _user_prompt(cv: StructuredCV, job: Job, score: ScoreResult, feedback: str = "") -> str:
    prompt = (
        f"JOB TITLE: {job.title}\nCOMPANY: {job.company}\n\nJOB DESCRIPTION:\n{job.description[:6000]}\n\n"
        f"THINGS THE JOB WANTS THAT THE CV DOES NOT SHOW (do not work these in): "
        f"{'; '.join(score.missing_requirements) or 'none listed'}\n\n"
        f"CV (JSON):\n{json.dumps(_compact(cv), ensure_ascii=False)}\n\n"
        "Return JSON with:\n"
        "- summary: 3 to 4 plain sentences about this person that fit this job, using only facts in the CV summary and experience.\n"
        "- skills: the same skill lines as the CV, with the most job-relevant lines first and the most relevant items first inside each line. Same line headings, only items already listed.\n"
        "- experience: for EVERY role index, all of its bullets, each as {source: original bullet number, text}. Put the bullets most relevant to this job first. Reword lightly only where it helps; keep bullets as they are if they already read well.\n"
    )
    if feedback:
        prompt += f"\nYour previous answer had these problems. Fix them and return the full JSON again:\n{feedback}\n"
    return prompt


def _short(text: str) -> str:
    return text if len(text) <= 70 else text[:67] + "..."


def _apply(out: TailorOutput, original: StructuredCV) -> tuple[StructuredCV, list[str], list[str], int]:
    """Returns (cv, changes, problems, reverted_bullets)."""
    whole = guard.cv_text(original)
    cv = original.model_copy(deep=True)
    changes: list[str] = []
    problems: list[str] = []
    reverted = 0

    problem = guard.check_summary(out.summary, original)
    if problem:
        problems.append(f"Summary: {problem}")
        changes.append(f"Summary kept as in your CV: the rewrite had a problem ({problem}).")
    elif out.summary.strip() != original.summary.strip():
        cv.summary = out.summary.strip()
        changes.append("Rewrote the career profile to fit the job, using only what your CV already says.")

    skills, notes = guard.guard_skills(out.skills, original)
    if skills != original.skills:
        cv.skills = skills
        changes.append("Reordered the skills so the ones this job asks for come first.")
    changes += notes

    roles = {r.index: r for r in out.experience}
    for i, role in enumerate(original.experience):
        proposed = roles.get(i)
        label = f"{role.title or 'Role'} at {role.company}"
        if proposed is None:
            changes.append(f"{label}: no changes returned, kept as in your CV.")
            continue
        used: set[int] = set()
        new_bullets: list[str] = []
        reworded = 0
        for b in proposed.bullets:
            if not 0 <= b.source < len(role.bullets) or b.source in used:
                continue
            used.add(b.source)
            src = role.bullets[b.source]
            text = b.text.strip()
            problem = guard.check_bullet(text, src, whole)
            if problem:
                problems.append(f"{label}, bullet {b.source}: {problem}")
                changes.append(f"{label}: kept original wording of '{_short(src)}' because the rewrite had a problem ({problem}).")
                reverted += 1
                text = src
            elif text != src:
                reworded += 1
            new_bullets.append(text)
        for j, src in enumerate(role.bullets):
            if j not in used:
                new_bullets.append(src)
        if shared_openers(new_bullets) and not shared_openers(role.bullets):
            problems.append(f"{label}: too many bullets start with the same word")
        order = [b.source for b in proposed.bullets if b.source in used]
        moved = order != sorted(order)
        if reworded or moved:
            parts = []
            if reworded:
                parts.append(f"reworded {reworded} bullet(s)")
            if moved:
                parts.append("moved the most relevant bullets up")
            changes.append(f"{label}: " + " and ".join(parts) + ".")
        cv.experience[i].bullets = new_bullets
    return cv, changes, problems, reverted


async def tailor_cv(cv: StructuredCV, job: Job, score: ScoreResult, out_dir: Path) -> TailoredCV:
    out_dir = Path(out_dir)
    out_path = out_dir / document_name("CV", cv.full_name, job.company, "docx")
    total_bullets = sum(len(r.bullets) for r in cv.experience) or 1

    def original(note: str) -> TailoredCV:
        write_cv_docx(cv, out_path)
        return TailoredCV(cv=cv, docx_path=str(out_path), changes=[note])

    try:
        out = await llm.complete_json(SYSTEM, _user_prompt(cv, job, score), TailorOutput, max_tokens=6000)
        tailored, changes, problems, reverted = _apply(out, cv)
        if problems:
            feedback = "\n".join(f"- {p}" for p in problems)
            out = await llm.complete_json(SYSTEM, _user_prompt(cv, job, score, feedback), TailorOutput, max_tokens=6000)
            tailored, changes, problems, reverted = _apply(out, cv)
    except Exception as err:  # noqa: BLE001
        return original(f"Your CV is unchanged: the AI step was unavailable ({err}).")

    if reverted / total_bullets > 0.5:
        return original("Your CV is unchanged: most of the AI rewrite was rejected for adding details not in your CV.")
    if not changes:
        changes = ["No edits were needed; your CV already reads well for this job."]
    write_cv_docx(tailored, out_path)
    return TailoredCV(cv=tailored, docx_path=str(out_path), changes=changes)
