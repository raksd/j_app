from fastapi import APIRouter, HTTPException, UploadFile

from app import config
from app.models import StructuredCV
from app.storage import json_store

router = APIRouter(prefix="/cv", tags=["cv"])


@router.post("/upload", response_model=StructuredCV)
async def upload_cv(file: UploadFile):
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "Please upload a .docx file")
    from app.services.cv import parse_cv_with_llm

    path = config.cv_dir() / "base.docx"
    path.write_bytes(await file.read())
    try:
        cv = await parse_cv_with_llm(path)
    except Exception as err:  # noqa: BLE001
        raise HTTPException(502, f"Could not parse CV: {err}") from err
    json_store.save_cv(cv)
    return cv


@router.get("", response_model=StructuredCV)
def get_cv():
    cv = json_store.load_cv()
    if cv is None:
        raise HTTPException(404, "No CV uploaded yet")
    return cv
