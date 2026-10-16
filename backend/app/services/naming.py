from __future__ import annotations

import re

MAX_PART = 40


def _clean(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")[:MAX_PART].strip("_")


def initials(full_name: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", full_name or "")).upper()


def document_name(kind: str, full_name: str, company: str, ext: str) -> str:
    """e.g. RD_CV_Acme_Ltd.docx; empty parts are left out."""
    parts = [initials(full_name), kind, _clean(company)]
    return "_".join(p for p in parts if p) + f".{ext}"
