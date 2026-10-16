from __future__ import annotations

from app.models import Job

from . import extract, safe_fetch
from .errors import JobLinkError
from .url import job_id_for, normalize_url, source_for

__all__ = ["JobLinkError", "job_from_url"]

_MISSING_FIELDS_MESSAGE = "Paste the job title and company along with the description."


async def _from_pasted(
    normalized: str, title: str, company: str, description: str
) -> Job:
    if not title and not company:
        found = await extract.infer_fields(description, normalized)
        title, company = found.title, found.company
        if not title and not company:
            raise JobLinkError(_MISSING_FIELDS_MESSAGE, needs_paste=True)
    return Job(
        id=job_id_for(normalized),
        source=source_for(normalized),
        title=title,
        company=company,
        work_mode=extract.infer_work_mode(f"{title}\n{description}"),  # type: ignore[arg-type]
        description=description,
        url=normalized,
    )


async def job_from_url(
    url: str,
    title: str | None = None,
    company: str | None = None,
    description: str | None = None,
) -> Job:
    normalized = normalize_url(url)
    pasted = (description or "").strip()
    if pasted:
        return await _from_pasted(
            normalized, (title or "").strip(), (company or "").strip(), pasted
        )

    page = await safe_fetch.fetch_html(normalized)
    data = await extract.extract_job(page.html, page.final_url)
    return Job(
        id=job_id_for(normalized),
        source=source_for(normalized),
        title=(title or "").strip() or data.title,
        company=(company or "").strip() or data.company,
        location=data.location,
        work_mode=extract.infer_work_mode(  # type: ignore[arg-type]
            f"{data.title}\n{data.location}\n{data.description}", data.remote
        ),
        description=data.description,
        url=normalized,
        posted_date=data.posted_date,
        salary=data.salary,
    )
