from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{job_id}/{filename}")
def download_file(job_id: str, filename: str):
    root = config.output_dir().resolve()
    path = (root / job_id / filename).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(400, "Invalid path")
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=path.name)
