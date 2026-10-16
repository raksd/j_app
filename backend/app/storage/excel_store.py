import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.datavalidation import DataValidation

from app import config
from app.models import ApplicationRecord, ApplicationStatus

SHEET = "Applications"
HEADERS = [
    "ID",
    "Date Applied",
    "Company",
    "Job Title",
    "Location",
    "Work Mode",
    "Job URL",
    "ATS Score",
    "Requirements Not Matched in CV",
    "CV File",
    "Cover Letter File",
    "Status",
    "Notes",
    "Last Updated",
]
WIDTHS = [38, 13, 24, 30, 20, 11, 40, 10, 50, 36, 36, 13, 30, 20]
URL_COL, STATUS_COL, NOTES_COL, UPDATED_COL = 7, 12, 13, 14
MAX_ROWS = 10000
EXCEL_EPOCH = datetime(1899, 12, 30)
DATE_FORMATS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)

logger = logging.getLogger(__name__)


class TrackerLockedError(RuntimeError):
    pass


class RecordNotFoundError(KeyError):
    pass


class TrackerRowError(RuntimeError):
    pass


def _normalize_work_mode(value) -> str:
    mode = str(value or "").strip().lower()
    valid = {"remote", "hybrid", "onsite", "any", "unknown"}
    return mode if mode in valid else "unknown"


def _normalize_status(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ApplicationStatus.APPLIED.value
    for status in ApplicationStatus:
        if raw.lower() == status.value.lower():
            return status.value
    return ApplicationStatus.APPLIED.value


def _build_workbook() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:N1"
    for i, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
    _apply_validation(ws)
    return wb


def _apply_validation(ws) -> None:
    """(Re)apply the status dropdown. Runs on every write so trackers created
    before this rule existed pick it up too."""
    ws.data_validations.dataValidation = []
    options = ",".join(s.value for s in ApplicationStatus)
    dv = DataValidation(type="list", formula1=f'"{options}"', allow_blank=True)
    dv.showErrorMessage = True
    dv.errorStyle = "stop"
    dv.errorTitle = "Invalid status"
    dv.error = f"Choose one of: {options}"
    dv.add(f"L2:L{MAX_ROWS}")
    ws.add_data_validation(dv)


def _save_atomic(wb: Workbook, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=path.parent)
    os.close(fd)
    try:
        wb.save(tmp)
        os.replace(tmp, path)
    except PermissionError as err:
        raise TrackerLockedError(
            f"Cannot write {path.name}: the file is open in Excel. Close it and try again."
        ) from err
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _open(path: Optional[Path] = None):
    path = path or config.tracker_path()
    if not path.exists():
        _save_atomic(_build_workbook(), path)
    wb = load_workbook(path)
    return wb, wb[SHEET], path


def _to_date(value) -> Optional[date]:
    """Read a date cell the way a person might have typed it. None if unreadable."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (EXCEL_EPOCH + timedelta(days=float(value))).date()
        except (OverflowError, ValueError):
            return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _to_datetime(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value or "").strip()
    if text:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
    day = _to_date(value)
    return datetime(day.year, day.month, day.day) if day else None


def _to_float(value, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value or "").strip().replace("%", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return default


def _row_to_record(row: tuple) -> Optional[ApplicationRecord]:
    """Build a record from a sheet row, or None if the row is beyond repair.

    The tracker is a file the user edits by hand, so one mistyped cell must never
    stop the other rows from loading.
    """
    id_ = row[0] if row else None
    try:
        (id_, applied, company, title, location, mode, url, score, missing, cv, cl, status, notes, updated) = row
        day = _to_date(applied)
        stamp = _to_datetime(updated)
        if day is None and stamp is not None:
            day = stamp.date()
        if stamp is None and day is not None:
            stamp = datetime(day.year, day.month, day.day)
        if day is None:
            logger.warning("Tracker row %r skipped: no readable date in 'Date Applied'", id_)
            return None
        return ApplicationRecord(
            id=str(id_),
            date_applied=day,
            company=company or "",
            job_title=title or "",
            location=location or "",
            work_mode=_normalize_work_mode(mode),
            job_url=url or "",
            ats_score=_to_float(score),
            requirements_not_matched=[m.strip() for m in str(missing).split(";") if m.strip()] if missing else [],
            cv_file=cv or "",
            cover_letter_file=cl or "",
            status=_normalize_status(status),
            notes=notes or "",
            last_updated=stamp,
        )
    except Exception:
        logger.warning("Tracker row %r skipped: could not be read", id_, exc_info=True)
        return None


def append_record(record: ApplicationRecord, path: Optional[Path] = None) -> ApplicationRecord:
    wb, ws, path = _open(path)
    try:
        ws.append(
            [
                record.id,
                record.date_applied.isoformat(),
                record.company,
                record.job_title,
                record.location,
                record.work_mode,
                record.job_url,
                record.ats_score,
                "; ".join(record.requirements_not_matched),
                record.cv_file,
                record.cover_letter_file,
                record.status.value,
                record.notes,
                record.last_updated.isoformat(timespec="seconds"),
            ]
        )
        if record.job_url:
            cell = ws.cell(row=ws.max_row, column=URL_COL)
            cell.hyperlink = record.job_url
            cell.font = Font(color="0563C1", underline="single")
        _apply_validation(ws)
        _save_atomic(wb, path)
        return record
    finally:
        wb.close()


def list_records(path: Optional[Path] = None) -> list[ApplicationRecord]:
    wb, ws, _ = _open(path)
    try:
        rows = [
            row
            for row in ws.iter_rows(min_row=2, max_col=len(HEADERS), values_only=True)
            if row[0]
        ]
        records = [rec for rec in (_row_to_record(row) for row in rows) if rec is not None]
        if len(records) < len(rows):
            logger.warning("Tracker: %d of %d rows could not be read", len(rows) - len(records), len(rows))
        return records
    finally:
        wb.close()


def update_status(
    record_id: str,
    status: ApplicationStatus,
    notes: Optional[str] = None,
    path: Optional[Path] = None,
) -> ApplicationRecord:
    wb, ws, path = _open(path)
    try:
        for row in ws.iter_rows(min_row=2, max_col=len(HEADERS)):
            if row[0].value == record_id:
                row[STATUS_COL - 1].value = ApplicationStatus(status).value
                if notes is not None:
                    row[NOTES_COL - 1].value = notes
                row[UPDATED_COL - 1].value = datetime.now().isoformat(timespec="seconds")
                record = _row_to_record(tuple(c.value for c in row))
                if record is None:
                    raise TrackerRowError(
                        f"The tracker row for {record_id} can't be read. "
                        "Open the tracker in Excel and check its Date Applied cell."
                    )
                _apply_validation(ws)
                _save_atomic(wb, path)
                return record
        raise RecordNotFoundError(record_id)
    finally:
        wb.close()
