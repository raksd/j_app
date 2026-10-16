from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CoverLetter, Job, PreparedApplication, ScoreResult, StructuredCV, TailoredCV
from app.storage import excel_store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(app)


def prepared(tmp_path, job_id="job1"):
    job = Job(
        id=job_id,
        source="fake",
        title="Engineer",
        company="Acme",
        location="London",
        work_mode="hybrid",
        url="https://x.test/1",
    )
    out = tmp_path / "output" / job_id
    return PreparedApplication(
        job=job,
        score=ScoreResult(
            ats_score=66, keyword_score=60, llm_score=70, missing_requirements=["Rust", "Kafka"]
        ),
        tailored_cv=TailoredCV(cv=StructuredCV(), docx_path=str(out / "cv.docx")),
        cover_letter=CoverLetter(text="orig", docx_path=str(out / "cover_letter.docx")),
    )


def test_create_list_and_patch(client, tmp_path):
    body = {
        "prepared": prepared(tmp_path).model_dump(mode="json"),
        "cover_letter_text": "Edited letter",
    }
    r = client.post("/api/applications", json=body)
    assert r.status_code == 200
    rec = r.json()
    assert rec["status"] == "Applied"
    assert rec["date_applied"] == date.today().isoformat()
    assert rec["requirements_not_matched"] == ["Rust", "Kafka"]
    assert rec["cv_file"] == "output/job1/cv.docx"
    assert rec["cover_letter_file"] == "output/job1/Cover_Letter_Acme.txt"
    assert (tmp_path / "output" / "job1" / "Cover_Letter_Acme.txt").read_text() == "Edited letter"
    from docx import Document

    docx_text = "\n".join(p.text for p in Document(str(tmp_path / "output" / "job1" / "Cover_Letter_Acme.docx")).paragraphs)
    assert "Edited letter" in docx_text
    assert (tmp_path / "tracker.xlsx").exists()

    listed = client.get("/api/applications").json()
    assert [a["id"] for a in listed] == [rec["id"]]
    assert listed[0]["company"] == "Acme"

    r = client.patch(f"/api/applications/{rec['id']}/status", json={"status": "Interview", "notes": "Call Mon"})
    assert r.status_code == 200
    assert r.json()["status"] == "Interview"
    assert r.json()["notes"] == "Call Mon"
    assert excel_store.list_records()[0].status.value == "Interview"


def test_patch_errors(client):
    assert client.patch("/api/applications/nope/status", json={"status": "Offer"}).status_code == 404
    assert client.patch("/api/applications/nope/status", json={"status": "Bogus"}).status_code == 422


def test_list_empty(client):
    assert client.get("/api/applications").json() == []


def test_locked_tracker_returns_423(client, tmp_path, monkeypatch):
    def locked(record, path=None):
        raise excel_store.TrackerLockedError("file is open in Excel")

    monkeypatch.setattr(excel_store, "append_record", locked)
    body = {"prepared": prepared(tmp_path).model_dump(mode="json"), "cover_letter_text": "x"}
    r = client.post("/api/applications", json=body)
    assert r.status_code == 423
    assert "Excel" in r.json()["detail"]


def test_duplicate_job_link_rejected(client, tmp_path):
    body = {"prepared": prepared(tmp_path).model_dump(mode="json"), "cover_letter_text": "x"}
    assert client.post("/api/applications", json=body).status_code == 200
    r = client.post("/api/applications", json=body)
    assert r.status_code == 409
    assert "already" in r.json()["detail"]
    assert len(client.get("/api/applications").json()) == 1


def test_unsafe_job_id_rejected(client, tmp_path):
    body = {"prepared": prepared(tmp_path, "../evil").model_dump(mode="json"), "cover_letter_text": "x"}
    assert client.post("/api/applications", json=body).status_code == 400
