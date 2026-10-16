from __future__ import annotations

from pathlib import Path

from app import llm
from app.models import StructuredCV

from . import parse
from .parse import parse_cv
from .tailor import tailor_cv
from .writer import write_cv_docx

__all__ = ["parse_cv", "parse_cv_with_llm", "tailor_cv", "write_cv_docx"]

PARSE_SYSTEM = (
    "Convert CV text into the JSON structure. Copy every piece of text exactly as written. "
    "Do not shorten, reword, correct or add anything. Put each skills line as one string. "
    "Use empty strings or lists for anything the CV does not contain."
)


async def parse_cv_with_llm(docx_path: Path) -> StructuredCV:
    lines = parse.read_lines(Path(docx_path))
    cv = parse.parse_lines(lines)
    if parse.looks_complete(cv):
        return cv
    try:
        return await llm.complete_json(PARSE_SYSTEM, "\n".join(lines), StructuredCV, max_tokens=6000)
    except Exception:  # noqa: BLE001
        return cv
