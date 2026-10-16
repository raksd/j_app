from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.models import StructuredCV

from .language import find_banned

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#./'’-]*")
NUMBER = re.compile(r"[£$€]?\d[\d,]*(?:\.\d+)?%?[kKmMbB]?")
NUMBER_WORDS = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "dozen",
    "hundred", "thousand", "million", "billion", "double", "triple", "twice",
}
SENIORITY = {"senior", "lead", "principal", "head", "director", "manager", "expert", "specialist", "chief"}


class TailorBullet(BaseModel):
    source: int
    text: str


class TailorRole(BaseModel):
    index: int
    bullets: list[TailorBullet] = Field(default_factory=list)


class TailorOutput(BaseModel):
    summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[TailorRole] = Field(default_factory=list)


def cv_text(cv: StructuredCV) -> str:
    parts = [cv.full_name, cv.headline, cv.summary, *cv.skills, *cv.certifications]
    for r in cv.experience:
        parts += [r.title, r.company, r.location, r.start, r.end, *r.bullets]
    for e in cv.education:
        parts += [e.qualification, e.institution, e.details]
    for p in cv.projects:
        parts += [p.name, p.description, *p.bullets]
    return "\n".join(x for x in parts if x)


def _words(text: str) -> set[str]:
    return {t.lower().strip(".'’-") for t in TOKEN.findall(text)}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").lower() for n in NUMBER.findall(text)}


def novel_terms(text: str, allowed_text: str) -> list[str]:
    allowed = _words(allowed_text)
    bad: list[str] = []
    for sentence in re.split(r"(?<=[.!?;:])\s+", text):
        for i, tok in enumerate(TOKEN.findall(sentence)):
            if i == 0:
                continue
            capital = tok[0].isupper() or any(c.isdigit() for c in tok)
            if capital and tok.lower().strip(".'’-") not in allowed:
                bad.append(tok)
    return bad


def unsupported_numbers(text: str, allowed_text: str) -> list[str]:
    allowed = _numbers(allowed_text)
    bad = [n for n in _numbers(text) if n not in allowed]
    allowed_words = _words(allowed_text)
    bad += [w for w in _words(text) if w in NUMBER_WORDS and w not in allowed_words]
    return bad


def check_bullet(new: str, source: str, whole_cv: str) -> str | None:
    if not new.strip():
        return "empty"
    nums = unsupported_numbers(new, source)
    if nums:
        return f"number or amount not in the original bullet ({', '.join(nums)})"
    terms = novel_terms(new, whole_cv)
    if terms:
        return f"new tool or term not in your CV ({', '.join(terms)})"
    banned = set(find_banned(new)) - set(find_banned(source))
    if banned:
        return f"buzzword wording ({', '.join(sorted(banned))})"
    return None


def check_summary(new: str, original: StructuredCV) -> str | None:
    whole = cv_text(original)
    if not new.strip():
        return "empty"
    nums = unsupported_numbers(new, whole)
    if nums:
        return f"number not in your CV ({', '.join(nums)})"
    terms = novel_terms(new, whole)
    if terms:
        return f"new tool or term not in your CV ({', '.join(terms)})"
    low_whole = _words(whole)
    claims = [w for w in _words(new) if w in SENIORITY and w not in low_whole]
    if claims:
        return f"seniority claim not in your CV ({', '.join(claims)})"
    banned = find_banned(new)
    if banned:
        return f"buzzword wording ({', '.join(sorted(set(banned)))})"
    return None


def _split_skill_line(line: str) -> tuple[str, list[str]]:
    label, body = (line.split(":", 1) + [""])[:2] if ":" in line else ("", line)
    items, depth, cur = [], 0, ""
    for ch in body:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth <= 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return label.strip(), items


def guard_skills(proposed: list[str], original: StructuredCV) -> tuple[list[str], list[str]]:
    notes: list[str] = []
    allowed_items: dict[str, str] = {}
    allowed_labels: dict[str, str] = {}
    for line in original.skills:
        label, items = _split_skill_line(line)
        if label:
            allowed_labels[label.lower()] = label
        for item in items:
            allowed_items[item.lower()] = item

    result: list[str] = []
    seen: set[str] = set()
    for line in proposed:
        label, items = _split_skill_line(line)
        if label and label.lower() not in allowed_labels:
            notes.append(f"Dropped skills line '{label}': not a heading in your CV")
            continue
        kept = []
        for item in items:
            canon = allowed_items.get(item.lower())
            if canon is None:
                notes.append(f"Removed skill '{item}': not listed in your CV")
            elif canon.lower() not in seen:
                seen.add(canon.lower())
                kept.append(canon)
        if kept:
            result.append((allowed_labels[label.lower()] + ": " if label else "") + ", ".join(kept))

    for line in original.skills:
        label, items = _split_skill_line(line)
        missing = [i for i in items if i.lower() not in seen]
        if not missing:
            continue
        seen.update(i.lower() for i in missing)
        notes.append(f"Kept {len(missing)} skill(s) the rewrite had left out ({', '.join(missing[:3])})")
        prefix = (label + ": ") if label else ""
        for idx, existing in enumerate(result):
            if prefix and existing.startswith(prefix):
                result[idx] = existing + ", " + ", ".join(missing)
                break
        else:
            result.append(prefix + ", ".join(missing))
    return result, notes
