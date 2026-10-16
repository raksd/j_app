from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.models import EducationItem, ExperienceItem, ProjectItem, StructuredCV

BULLET_CHARS = "•-*▪●◦·–"
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE = rf"(?:{MONTH}\s+)?\d{{4}}"
DATE_RANGE = re.compile(rf"({DATE})\s*(?:–|—|-|to)\s*({DATE}|Present|Current|Now)", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s()-]{8,}\d")
LINK = re.compile(r"(?:https?://|www\.)\S+|(?:linkedin|github)\.com/\S+", re.IGNORECASE)
TITLE_WORDS = (
    "engineer scientist analyst manager pharmacist developer consultant officer lead director "
    "assistant specialist technician nurse administrator researcher intern associate"
).split()

SECTION_KEYS = [
    ("education", ("education", "qualification")),
    ("experience", ("experience", "employment", "work history", "career history")),
    ("projects", ("project",)),
    ("certifications", ("certif", "licen", "training")),
    ("skills", ("skill", "competenc", "technolog", "expertise")),
    ("summary", ("profile", "summary", "objective", "about")),
]


def read_lines(docx_path: Path) -> list[str]:
    doc = Document(str(docx_path))
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, doc).text.strip()
            if text:
                lines.append(text)
        elif child.tag == qn("w:tbl"):
            for row in Table(child, doc).rows:
                unique = []
                for cell in row.cells:
                    if cell._tc not in [c._tc for c in unique]:
                        unique.append(cell)
                if len(unique) == 1:
                    lines.extend(t for t in (" ".join(p.text.split()) for p in unique[0].paragraphs) if t)
                    continue
                cells: list[str] = []
                for cell in unique:
                    text = " ".join(cell.text.split())
                    if text and text not in cells:
                        cells.append(text)
                if cells:
                    lines.append(" | ".join(cells))
    return lines


def _section_of(line: str) -> str | None:
    if len(line.split()) > 5 or ":" in line or line.endswith("."):
        return None
    low = line.lower()
    for name, keys in SECTION_KEYS:
        if any(k in low for k in keys):
            return name
    return None


def _strip_bullet(line: str) -> str:
    return line.lstrip(BULLET_CHARS + " \t").strip()


def _split_company(text: str) -> tuple[str, str]:
    if "," in text:
        company, tail = text.rsplit(",", 1)
        if len(tail.split()) <= 3:
            return company.strip(), tail.strip()
    return text.strip(), ""


def _looks_like_title(text: str) -> bool:
    return any(w in text.lower().split() for w in TITLE_WORDS)


def _parse_experience(lines: list[str]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    current: ExperienceItem | None = None
    for line in lines:
        match = DATE_RANGE.search(line)
        is_header = bool(match) and len(line) < 160 and len(line.split()) <= 18
        if is_header:
            rest = (line[: match.start()] + " " + line[match.end() :]).strip()
            parts = [p.strip(" ,-–—") for p in rest.split("|") if p.strip(" ,-–—")]
            title, company, location = "", "", ""
            for part in parts:
                if _looks_like_title(part) and not title:
                    title = part
                elif not company:
                    company, location = _split_company(part)
            current = ExperienceItem(
                title=title, company=company, location=location,
                start=match.group(1), end=match.group(2),
            )
            items.append(current)
        elif current is not None:
            text = _strip_bullet(line)
            if not current.title and not current.bullets and len(text.split()) <= 8 and not text.endswith("."):
                current.title = text
            else:
                current.bullets.append(text)
    return items


def _parse_education(lines: list[str]) -> list[EducationItem]:
    items = []
    for line in lines:
        text = _strip_bullet(line)
        dates = DATE_RANGE.search(text)
        start, end = (dates.group(1), dates.group(2)) if dates else ("", "")
        if dates:
            text = (text[: dates.start()] + text[dates.end() :]).strip(" |,-–—")
        parts = re.split(r"\s[—–-]\s", text, maxsplit=1)
        if len(parts) == 2:
            items.append(EducationItem(institution=parts[0].strip(), qualification=parts[1].strip(), start=start, end=end))
        else:
            items.append(EducationItem(institution="", qualification=text, start=start, end=end))
    return items


def _parse_projects(lines: list[str]) -> list[ProjectItem]:
    items = []
    for line in lines:
        text = _strip_bullet(line)
        if ":" in text and len(text.split(":", 1)[0].split()) <= 8:
            name, desc = text.split(":", 1)
            items.append(ProjectItem(name=name.strip(), description=desc.strip()))
        else:
            items.append(ProjectItem(name=text))
    return items


def parse_lines(lines: list[str]) -> StructuredCV:
    cv = StructuredCV()
    sections: dict[str, list[str]] = {}
    header: list[str] = []
    current: str | None = None
    for line in lines:
        name = _section_of(line)
        if name:
            current = name
            sections.setdefault(name, [])
        elif current is None:
            header.append(line)
        else:
            sections[current].append(line)

    if header:
        cv.full_name = header[0]
        for line in header[1:]:
            email, phone = EMAIL.search(line), PHONE.search(line)
            cv.links += [m.rstrip(".,)") for m in LINK.findall(line) if m not in cv.links]
            if email or phone:
                cv.email = cv.email or (email.group(0) if email else "")
                cv.phone = cv.phone or (phone.group(0).strip() if phone else "")
                for seg in re.split(r"\s*[|•·]\s*", line):
                    if seg and not EMAIL.search(seg) and not PHONE.search(seg) and not LINK.search(seg):
                        cv.location = cv.location or seg.strip()
            elif not cv.headline:
                cv.headline = line

    cv.summary = " ".join(sections.get("summary", []))
    cv.skills = [_strip_bullet(s) for s in sections.get("skills", [])]
    cv.experience = _parse_experience(sections.get("experience", []))
    cv.education = _parse_education(sections.get("education", []))
    cv.projects = _parse_projects(sections.get("projects", []))
    cv.certifications = [_strip_bullet(c) for c in sections.get("certifications", [])]
    return cv


def parse_cv(docx_path: Path) -> StructuredCV:
    return parse_lines(read_lines(Path(docx_path)))


def looks_complete(cv: StructuredCV) -> bool:
    return bool(cv.full_name and cv.skills and cv.experience and any(e.bullets for e in cv.experience))
