import sys
import types

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CoverLetter, Job, ScoreResult, StructuredCV, TailoredCV
from app.storage import json_store


def make_job(n):
    return Job(id=f"job{n}", source="fake", title=f"Title {n}", company="Co", url=f"https://x.test/{n}")


def make_score(value):
    return ScoreResult(ats_score=value, keyword_score=value, llm_score=value)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(app)


def install(monkeypatch, name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)


def test_prepare(client, tmp_path, monkeypatch):
    json_store.save_cv(StructuredCV(full_name="Ann"))
    job = make_job(1)
    seen = {}

    async def score_job(cv, job):
        return make_score(80)

    async def tailor_cv(cv, job, score, out_dir):
        seen["tailor_dir"] = out_dir
        path = out_dir / "cv.docx"
        path.write_bytes(b"cv")
        return TailoredCV(cv=cv, docx_path=str(path), changes=["reworded"])

    async def write_cover_letter(cv, job, score, out_dir):
        seen["letter_dir"] = out_dir
        return CoverLetter(text="Dear team", docx_path=str(out_dir / "cover_letter.docx"))

    install(monkeypatch, "app.services.scoring", score_cv=score_job)
    install(monkeypatch, "app.services.cover_letter", write_cover_letter=write_cover_letter)
    install(monkeypatch, "app.services.cv", tailor_cv=tailor_cv)

    r = client.post("/api/jobs/prepare", json={"job": job.model_dump(mode="json")})
    assert r.status_code == 200
    body = r.json()
    assert body["score"]["ats_score"] == 80
    assert body["tailored_cv"]["changes"] == ["reworded"]
    assert body["cover_letter"]["text"] == "Dear team"
    assert seen["tailor_dir"] == seen["letter_dir"] == (tmp_path / "output" / "job1").resolve()


def test_prepare_reports_cover_letter_failure(client, monkeypatch):
    json_store.save_cv(StructuredCV(full_name="Ann"))

    async def score_job(cv, job):
        return make_score(80)

    async def tailor_cv(cv, job, score, out_dir):
        return TailoredCV(cv=cv, docx_path=str(out_dir / "cv.docx"))

    async def write_cover_letter(cv, job, score, out_dir):
        raise RuntimeError("No cover letter was written")

    install(monkeypatch, "app.services.scoring", score_cv=score_job)
    install(monkeypatch, "app.services.cover_letter", write_cover_letter=write_cover_letter)
    install(monkeypatch, "app.services.cv", tailor_cv=tailor_cv)
    r = client.post("/api/jobs/prepare", json={"job": make_job(1).model_dump(mode="json")})
    assert r.status_code == 502
    assert "No cover letter" in r.json()["detail"]


def test_prepare_requires_cv_and_safe_id(client):
    assert client.post("/api/jobs/prepare", json={"job": make_job(1).model_dump(mode="json")}).status_code == 409
    bad = make_job(1).model_copy(update={"id": "../evil"})
    assert client.post("/api/jobs/prepare", json={"job": bad.model_dump(mode="json")}).status_code == 400


class FakeJobLinkError(Exception):
    def __init__(self, message, needs_paste):
        super().__init__(message)
        self.message = message
        self.needs_paste = needs_paste


def test_from_url_returns_job_without_cv_or_scoring(client, monkeypatch):
    seen = {}

    async def job_from_url(url, title=None, company=None, description=None):
        seen.update(url=url, title=title, company=company, description=description)
        return make_job(7).model_copy(update={"id": "m_abc123", "url": url})

    async def score_job(cv, job):
        raise AssertionError("adding a link must not score the job")

    install(monkeypatch, "app.services.manual", job_from_url=job_from_url, JobLinkError=FakeJobLinkError)
    install(monkeypatch, "app.services.scoring", score_cv=score_job)

    body = {"url": "https://www.linkedin.com/jobs/view/1", "title": "Dev", "company": "Acme", "description": "text"}
    r = client.post("/api/jobs/from-url", json=body)
    assert r.status_code == 200
    assert r.json()["id"] == "m_abc123"
    assert seen == {"url": body["url"], "title": "Dev", "company": "Acme", "description": "text"}


def test_from_url_error_mapping(client, monkeypatch):
    def raising(err):
        async def job_from_url(url, title=None, company=None, description=None):
            raise err

        return job_from_url

    req = {"url": "https://x.test/job"}

    install(monkeypatch, "app.services.manual", job_from_url=raising(FakeJobLinkError("login", True)), JobLinkError=FakeJobLinkError)
    r = client.post("/api/jobs/from-url", json=req)
    assert r.status_code == 422
    assert r.json()["detail"] == "login"

    install(monkeypatch, "app.services.manual", job_from_url=raising(FakeJobLinkError("bad url", False)), JobLinkError=FakeJobLinkError)
    assert client.post("/api/jobs/from-url", json=req).status_code == 400
