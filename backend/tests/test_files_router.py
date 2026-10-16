import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(app)


def test_downloads_file_inside_output(client, data_dir):
    folder = data_dir / "output" / "job1"
    folder.mkdir(parents=True)
    (folder / "cover_letter.txt").write_text("hello")
    r = client.get("/api/files/job1/cover_letter.txt")
    assert r.status_code == 200
    assert r.text == "hello"


def test_missing_file_404(client):
    assert client.get("/api/files/job1/nope.txt").status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "/api/files/job1/..%2F..%2Fsecret.txt",
        "/api/files/job1/%2e%2e%2f%2e%2e%2fsecret.txt",
        "/api/files/..%2F/secret.txt",
        "/api/files/job1/..%5C..%5Csecret.txt",
        "/api/files/job1/..%2F..%2F..%2Ftracker.xlsx",
    ],
)
def test_traversal_rejected(client, data_dir, url):
    (data_dir / "secret.txt").write_text("secret")
    (data_dir / "tracker.xlsx").write_text("x")
    (data_dir / "output" / "job1").mkdir(parents=True)
    r = client.get(url)
    assert r.status_code in (400, 404)
    assert "secret" not in r.text


def test_traversal_via_resolve_check(client, data_dir):
    from app.routers.files import download_file
    from fastapi import HTTPException

    (data_dir / "secret.txt").write_text("secret")
    with pytest.raises(HTTPException) as exc:
        download_file("..", "secret.txt")
    assert exc.value.status_code == 400
