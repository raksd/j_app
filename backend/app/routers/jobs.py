import asyncio
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config
from app.models import Job, PreparedApplication
from app.storage import json_store

router = APIRouter(prefix="/jobs", tags=["jobs"])

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class PrepareRequest(BaseModel):
    job: Job


class FromUrlRequest(BaseModel):
    url: str
    title: str | None = None
    company: str | None = None
    description: str | None = None


def _require_cv():
    cv = json_store.load_cv()
    if cv is None:
        raise HTTPException(409, "No CV uploaded yet. Upload your CV before searching or preparing.")
    return cv


@router.post("/from-url", response_model=Job)
async def from_url(req: FromUrlRequest):
    from app.services.manual import JobLinkError, job_from_url

    try:
        return await job_from_url(req.url, req.title, req.company, req.description)
    except JobLinkError as err:
        raise HTTPException(422 if err.needs_paste else 400, err.message) from err


@router.post("/prepare", response_model=PreparedApplication)
async def prepare(req: PrepareRequest):
    job = req.job
    if not SAFE_ID.match(job.id):
        raise HTTPException(400, "Invalid job id")
    cv = _require_cv()

    from app.services.cover_letter import write_cover_letter
    from app.services.cv import tailor_cv
    from app.services.scoring import score_cv

    out_dir = config.output_dir() / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        score = await score_cv(cv, job)
        tailored, letter = await asyncio.gather(
            tailor_cv(cv, job, score, out_dir),
            write_cover_letter(cv, job, score, out_dir),
        )
    except Exception as err:  # noqa: BLE001
        raise HTTPException(502, f"Preparing application failed: {err}") from err

    return PreparedApplication(job=job, score=score, tailored_cv=tailored, cover_letter=letter)
