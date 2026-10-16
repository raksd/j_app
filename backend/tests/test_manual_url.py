import pytest

from app.services.manual import JobLinkError
from app.services.manual.url import job_id_for, normalize_url, source_for


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("HTTPS://Example.COM/Jobs/123#apply", "https://example.com/Jobs/123"),
        ("https://example.com/jobs/123/", "https://example.com/jobs/123"),
        ("https://example.com", "https://example.com/"),
        (
            "https://example.com/jobs/1?utm_source=x&utm_medium=y&gclid=z&fbclid=q&id=7",
            "https://example.com/jobs/1?id=7",
        ),
        ("https://example.com/j?b=2&a=1&trk=abc&refId=r&trackingId=t&ref=x", "https://example.com/j?a=1&b=2"),
        ("https://example.com:443/jobs", "https://example.com/jobs"),
        ("http://example.com:80/jobs", "http://example.com/jobs"),
        ("https://example.com:8443/jobs", "https://example.com:8443/jobs"),
        (
            "https://www.linkedin.com/jobs/view/3812345678/?trk=public_jobs&refId=abc&trackingId=zz",
            "https://www.linkedin.com/jobs/view/3812345678",
        ),
        (
            "https://uk.linkedin.com/jobs/view/senior-engineer-at-acme-3812345678?position=1&pageNum=0",
            "https://www.linkedin.com/jobs/view/3812345678",
        ),
        (
            "https://www.linkedin.com/jobs/search/?keywords=python&currentJobId=3812345678&geoId=1",
            "https://www.linkedin.com/jobs/view/3812345678",
        ),
        (
            "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=99",
            "https://www.linkedin.com/jobs/view/99",
        ),
        (
            "https://uk.indeed.com/jobs?q=python&vjk=abcdef123456",
            "https://uk.indeed.com/viewjob?jk=abcdef123456",
        ),
        (
            "https://uk.indeed.com/viewjob?jk=abcdef123456&tk=x&from=serp",
            "https://uk.indeed.com/viewjob?jk=abcdef123456",
        ),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "ftp://example.com/x", "javascript:alert(1)", "file:///etc/passwd", "example.com/jobs", "https://"],
)
def test_normalize_rejects_invalid(raw):
    with pytest.raises(JobLinkError) as exc:
        normalize_url(raw)
    assert exc.value.needs_paste is False
    assert exc.value.message


def test_id_is_stable_and_ignores_tracking():
    a = job_id_for(normalize_url("https://www.linkedin.com/jobs/view/3812345678/?trk=a"))
    b = job_id_for(normalize_url("https://uk.linkedin.com/jobs/view/some-title-3812345678?refId=b#x"))
    c = job_id_for(normalize_url("https://www.linkedin.com/jobs/search?currentJobId=3812345678"))
    assert a == b == c
    assert a.startswith("m_") and len(a) == 18
    assert a != job_id_for(normalize_url("https://www.linkedin.com/jobs/view/3812345679"))


def test_source_strips_www():
    assert source_for(normalize_url("https://www.linkedin.com/jobs/view/1")) == "linkedin.com"
    assert source_for(normalize_url("https://careers.acme.com/jobs/1")) == "careers.acme.com"
    assert source_for(normalize_url("https://uk.indeed.com/viewjob?jk=a")) == "uk.indeed.com"
