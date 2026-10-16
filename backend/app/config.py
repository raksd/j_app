import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_DIR / ".env")


def data_dir() -> Path:
    """Resolve DATA_DIR on every call (so tests can override it) and ensure subdirs exist."""
    raw = os.environ.get("DATA_DIR", "../data")
    path = Path(raw)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    path = path.resolve()
    (path / "cv").mkdir(parents=True, exist_ok=True)
    (path / "output").mkdir(parents=True, exist_ok=True)
    return path


def output_dir() -> Path:
    return data_dir() / "output"


def cv_dir() -> Path:
    return data_dir() / "cv"


def tracker_path() -> Path:
    return data_dir() / "tracker.xlsx"
