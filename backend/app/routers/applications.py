import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config
from app.models import ApplicationRecord, ApplicationStatus, PreparedApplication
from app.routers.jobs import SAFE_ID
from app.storage import excel_store

router = APIRouter(prefix="/applications", tags=["applications"])


class CreateRequest(BaseModel):
    prepared: PreparedApplication
    cover_letter_text: str


class StatusRequest(BaseModel):
    status: ApplicationStatus
    notes: Optional[str] = None


def _relative_to_data(path_str: str) -> str:
    if not path_str:
        return ""
    data = config.data_dir()
    path = Path(path_str)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(data).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _locked_guard(fn, *args):
    try:
        return fn(*args)
    except excel_store.TrackerLockedError as err:
        raise HTTPException(423, str(err)) from err
    except excel_store.TrackerRowError as err:
        raise HTTPException(422, str(err)) from err


@router.post("", response_model=ApplicationRecord)
def create_application(req: CreateRequest):
    prepared = req.prepared
    job = prepared.job
    if not SAFE_ID.match(job.id):
        raise HTTPException(400, "Invalid job id")

    existing = _locked_guard(excel_store.list_records)
    if any(r.job_url == job.url for r in existing):
        raise HTTPException(409, "You already logged an application for this job link.")

    out_dir = config.output_dir() / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    from app.services.cover_letter import save_cover_letter

    save_cover_letter(req.cover_letter_text, prepared.tailored_cv.cv, out_dir)
    letter_txt = out_dir / "cover_letter.txt"

    record = ApplicationRecord(
        id=str(uuid.uuid4()),
        date_applied=date.today(),
        company=job.company,
        job_title=job.title,
        location=job.location,
        work_mode=job.work_mode,
        job_url=job.url,
        ats_score=prepared.score.ats_score,
        requirements_not_matched=prepared.score.missing_requirements,
        cv_file=_relative_to_data(prepared.tailored_cv.docx_path),
        cover_letter_file=_relative_to_data(str(letter_txt)),
        status=ApplicationStatus.APPLIED,
        notes="",
        last_updated=datetime.now().replace(microsecond=0),
    )
    return _locked_guard(excel_store.append_record, record)


@router.get("", response_model=list[ApplicationRecord])
def list_applications():
    return _locked_guard(excel_store.list_records)


@router.patch("/{application_id}/status", response_model=ApplicationRecord)
def patch_status(application_id: str, req: StatusRequest):
    try:
        return _locked_guard(excel_store.update_status, application_id, req.status, req.notes)
    except excel_store.RecordNotFoundError as err:
        raise HTTPException(404, "Application not found") from err
