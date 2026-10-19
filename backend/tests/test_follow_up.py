from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ApplicationRecord, ApplicationStatus, needs_follow_up
from app.storage import excel_store

TODAY = date(2026, 10, 16)


@pytest.mark.parametrize(
    "status,days_ago,expected",
    [
        (ApplicationStatus.APPLIED, 7, True),
        (ApplicationStatus.APPLIED, 30, True),
        (ApplicationStatus.APPLIED, 6, False),
        (ApplicationStatus.APPLIED, 0, False),
        (ApplicationStatus.INTERVIEW, 30, False),
        (ApplicationStatus.REJECTED, 30, False),
        (ApplicationStatus.NO_RESPONSE, 30, False),
    ],
)
def test_needs_follow_up(status, days_ago, expected):
    assert needs_follow_up(status, TODAY - timedelta(days=days_ago), TODAY) is expected


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(app)


def add(id_, days_ago, status):
    excel_store.append_record(
        ApplicationRecord(
            id=id_,
            date_applied=date.today() - timedelta(days=days_ago),
            company="Acme",
            job_title="Engineer",
            job_url=f"https://x.test/{id_}",
            ats_score=50,
            status=status,
            last_updated=datetime(2026, 10, 1, 9, 0, 0),
        )
    )


def test_list_flags_only_stale_applied_rows(client):
    add("old", 10, ApplicationStatus.APPLIED)
    add("new", 1, ApplicationStatus.APPLIED)
    add("old-interview", 10, ApplicationStatus.INTERVIEW)

    flags = {a["id"]: a["follow_up_due"] for a in client.get("/api/applications").json()}

    assert flags == {"old": True, "new": False, "old-interview": False}
