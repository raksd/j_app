import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from app import config
from app.models import StructuredCV


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _cv_path() -> Path:
    return config.cv_dir() / "structured.json"


def load_cv() -> Optional[StructuredCV]:
    path = _cv_path()
    if not path.exists():
        return None
    return StructuredCV.model_validate_json(path.read_text(encoding="utf-8"))


def save_cv(cv: StructuredCV) -> None:
    _write_json(_cv_path(), cv.model_dump(mode="json"))
