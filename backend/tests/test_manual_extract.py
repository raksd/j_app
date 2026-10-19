import asyncio
import json
from datetime import date

import pytest

from app import llm
from app.services import manual
from app.services.manual import JobLinkError, extract, safe_fetch
from app.services.manual.url import job_id_for, normalize_url

DESC = (
    "We are looking for a Python engineer to build data pipelines and APIs. "
    "You will work with a small team on cloud infrastructure, write tests, and review code. "
    "Requirements: 3 years of Python, SQL, and experience with FastAPI or similar frameworks."
)


def jsonld_page(payload, extra=""):
    return (
        "<html><head><title>Ignored</title>"
        f'<script type="application/ld+json">{json.dumps(payload)}</script>{extra}'
        "</head><body><p>Body text</p></body></html>"
    )


POSTING = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Senior Python Engineer",
    "hiringOrganization": {"@type": "Organization", "name": "Acme Ltd"},
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "London",
            "addressRegion": "England",
            "addressCountry": "GB",
        },
    },
    "description": "<p>" + DESC + "</p><ul><li>Python</li><li>SQL</li></ul>",
    "datePosted": "2026-09-30T08:00:00Z",
    "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "GBP",
        "value": {"@type": "QuantitativeValue", "minValue": 60000, "maxValue": 75000, "unitText": "YEAR"},
    },
}


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(llm, "complete_json", boom)


def serve(monkeypatch, html, final_url=None):
    async def fake(url, transport=None):
        return safe_fetch.FetchedPage(final_url=final_url or url, html=html)

    monkeypatch.setattr(safe_fetch, "fetch_html", fake)


def run(coro):
    return asyncio.run(coro)


def test_jsonld_extraction(monkeypatch):
    serve(monkeypatch, jsonld_page(POSTING))
    job = run(manual.job_from_url("https://www.example.com/jobs/1?utm_source=x"))
    assert job.title == "Senior Python Engineer"
    assert job.company == "Acme Ltd"
    assert job.location == "London, England, GB"
    assert job.source == "example.com"
    assert job.url == "https://www.example.com/jobs/1"
    assert job.id == job_id_for(normalize_url("https://www.example.com/jobs/1"))
    assert job.posted_date == date(2026, 9, 30)
    assert job.salary == "GBP 60000-75000 per year"
    assert "<" not in job.description and "Python engineer" in job.description
    assert "Python" in job.description and "SQL" in job.description
    assert job.work_mode == "unknown"


def test_jsonld_graph_list_and_html_escaped_description(monkeypatch):
    posting = dict(POSTING, description="&lt;p&gt;" + DESC + "&lt;/p&gt;", jobLocationType="TELECOMMUTE")
    page = jsonld_page({"@context": "https://schema.org", "@graph": [{"@type": "WebSite"}, posting]})
    serve(monkeypatch, page)
    job = run(manual.job_from_url("https://example.com/jobs/2"))
    assert job.title == "Senior Python Engineer"
    assert "&lt;" not in job.description and "<p>" not in job.description
    assert job.work_mode == "remote"

    page = jsonld_page([{"@type": ["Thing", "JobPosting"], **{k: v for k, v in posting.items() if k != "@type"}}])
    serve(monkeypatch, page)
    assert run(manual.job_from_url("https://example.com/jobs/2")).company == "Acme Ltd"


def test_hybrid_beats_remote_flag(monkeypatch):
    posting = dict(POSTING, jobLocationType="TELECOMMUTE", description=DESC + " This is a hybrid role, 2 days in office.")
    serve(monkeypatch, jsonld_page(posting))
    assert run(manual.job_from_url("https://example.com/jobs/3")).work_mode == "hybrid"


def test_work_mode_keyword_rules():
    assert extract.infer_work_mode("Fully remote position") == "remote"
    assert extract.infer_work_mode("Not remote, on-site only") == "onsite"
    assert extract.infer_work_mode("Remote or hybrid") == "hybrid"
    assert extract.infer_work_mode("nothing relevant") == "unknown"
    assert extract.infer_work_mode("nothing relevant", remote_flag=True) == "remote"


def test_invalid_jsonld_is_skipped(monkeypatch):
    page = (
        '<html><head><script type="application/ld+json">{not json</script></head>'
        f"<body><p>{DESC}</p></body></html>"
    )
    serve(monkeypatch, page)
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/jobs/4"))
    assert exc.value.needs_paste is True


def test_opengraph_fallback(monkeypatch):
    page = (
        "<html><head><title>Page title</title>"
        '<meta property="og:title" content="Data Analyst">'
        f'<meta property="og:description" content="{DESC}">'
        '<meta property="og:site_name" content="Example Jobs">'
        "</head><body></body></html>"
    )
    serve(monkeypatch, page)
    job = run(manual.job_from_url("https://example.com/jobs/5"))
    assert job.title == "Data Analyst"
    assert job.description == DESC
    assert job.company == ""
    assert job.location == ""
    assert job.posted_date is None and job.salary is None


def test_llm_fallback_fills_from_page_text(monkeypatch):
    page = (
        "<html><head><title>Job</title></head><body><nav>Menu Home</nav>"
        "<h1>Platform Engineer</h1><h2>Globex Corporation</h2><p>Leeds, United Kingdom</p>"
        f"<div>{DESC}</div><script>var x = 1;</script></body></html>"
    )
    serve(monkeypatch, page)
    seen = {}

    async def fake_complete_json(system, user, schema, max_tokens=4000):
        seen["system"], seen["user"] = system, user
        return schema(
            title="Platform Engineer",
            company="Globex Corporation",
            location="Leeds, United Kingdom",
            description=DESC,
        )

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    job = run(manual.job_from_url("https://example.com/jobs/6"))
    assert (job.title, job.company, job.location) == ("Platform Engineer", "Globex Corporation", "Leeds, United Kingdom")
    assert job.description == DESC
    assert "never infer" in seen["system"].lower()
    assert "var x" not in seen["user"] and "Platform Engineer" in seen["user"]


def test_llm_values_not_on_page_are_dropped(monkeypatch):
    page = (
        "<html><head><title>x</title></head><body>"
        f"<h1>Platform Engineer</h1><div>{DESC}</div></body></html>"
    )
    serve(monkeypatch, page)

    async def fake_complete_json(system, user, schema, max_tokens=4000):
        return schema(
            title="Platform Engineer",
            company="Invented Corp",
            location="Mars",
            description="Totally made up description that is not on the page at all.",
        )

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    job = run(manual.job_from_url("https://example.com/jobs/7"))
    assert job.title == "Platform Engineer"
    assert job.company == "" and job.location == ""
    assert "made up" not in job.description


def test_never_invents_when_page_lacks_fields(monkeypatch):
    posting = {"@type": "JobPosting", "title": "Support Agent", "description": DESC}
    serve(monkeypatch, jsonld_page(posting))
    job = run(manual.job_from_url("https://example.com/jobs/8"))
    assert job.company == "" and job.location == ""
    assert job.posted_date is None and job.salary is None
    assert job.work_mode == "unknown"


def test_llm_exception_is_swallowed(monkeypatch):
    posting = {"@type": "JobPosting", "title": "Support Agent", "description": DESC}
    serve(monkeypatch, jsonld_page(posting))
    job = run(manual.job_from_url("https://example.com/jobs/9"))
    assert job.title == "Support Agent"


@pytest.mark.parametrize(
    "final_url",
    [
        "https://www.linkedin.com/authwall?trk=x",
        "https://www.linkedin.com/login",
        "https://example.com/account/signin?next=/jobs/1",
        "https://www.linkedin.com/uas/login?session_redirect=x",
    ],
)
def test_login_wall_by_final_url(monkeypatch, final_url):
    serve(monkeypatch, jsonld_page(POSTING), final_url=final_url)
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://www.linkedin.com/jobs/view/3812345678"))
    assert exc.value.needs_paste is True
    assert exc.value.message.startswith("Could not read this job page (it may need a login).")
    assert "Paste the job title, company and description" in exc.value.message


@pytest.mark.parametrize(
    "text",
    [
        "Sign in to view more about this job",
        "Join to view the full job description",
        "Please enable JavaScript to continue",
        "Please complete the CAPTCHA below",
        "Verify you are human",
    ],
)
def test_login_wall_by_text(monkeypatch, text):
    page = f"<html><head><title>Job</title></head><body><h1>Engineer</h1><p>{text}</p><p>{DESC}</p></body></html>"
    serve(monkeypatch, page)
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/jobs/10"))
    assert exc.value.needs_paste is True
    assert "may need a login" in exc.value.message


def test_noscript_javascript_notice_detected(monkeypatch):
    page = (
        "<html><head><title>Job</title></head><body>"
        "<noscript>Please enable JavaScript to view this page.</noscript></body></html>"
    )
    serve(monkeypatch, page)
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/jobs/11"))
    assert exc.value.needs_paste is True


def test_wall_text_ignored_when_structured_posting_is_complete(monkeypatch):
    posting = dict(POSTING, description=DESC + " Apply without a captcha, just email us.")
    serve(monkeypatch, jsonld_page(posting, extra="<meta name='x' content='sign in to view'>"))
    job = run(manual.job_from_url("https://example.com/jobs/12"))
    assert job.title == "Senior Python Engineer"


def test_llm_not_called_for_login_wall(monkeypatch):
    called = []

    async def fake_complete_json(*args, **kwargs):
        called.append(1)
        raise AssertionError

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    serve(monkeypatch, "<html><body><h1>Sign in to view this job</h1></body></html>")
    with pytest.raises(JobLinkError):
        run(manual.job_from_url("https://example.com/jobs/13"))
    assert not called


def test_short_description_detected(monkeypatch):
    posting = {"@type": "JobPosting", "title": "Cook", "description": "Great job, apply now."}
    serve(monkeypatch, jsonld_page(posting))
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/jobs/14"))
    assert exc.value.needs_paste is True
    assert "Paste the job title, company and description" in exc.value.message


def test_empty_page_detected(monkeypatch):
    serve(monkeypatch, "<html><body></body></html>")
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/jobs/15"))
    assert exc.value.needs_paste is True


def test_missing_title_asks_for_paste(monkeypatch):
    serve(monkeypatch, f"<html><body><div>{DESC}</div></body></html>")

    async def fake_complete_json(system, user, schema, max_tokens=4000):
        return schema(description=DESC)

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/jobs/16"))
    assert exc.value.needs_paste is True and "title" in exc.value.message


LINKEDIN_TITLE = "JPMorganChase hiring Applied AI ML - Associate/VP in Greater London, England, United Kingdom | LinkedIn"


def linkedin_page(title=LINKEDIN_TITLE):
    return f"<html><head><title>{title}</title></head><body><div>{DESC}</div></body></html>"


def test_split_linkedin_title_gives_company_title_and_location():
    assert extract.split_linkedin_title(LINKEDIN_TITLE) == (
        "JPMorganChase",
        "Applied AI ML - Associate/VP",
        "Greater London, England, United Kingdom",
    )


def test_split_linkedin_title_keeps_in_inside_the_job_title():
    assert extract.split_linkedin_title("Acme Ltd hiring Engineer in Test in Leeds, England | LinkedIn") == (
        "Acme Ltd",
        "Engineer in Test",
        "Leeds, England",
    )


def test_split_linkedin_title_without_location():
    assert extract.split_linkedin_title("Acme Ltd hiring Data Scientist | LinkedIn") == ("Acme Ltd", "Data Scientist", "")


@pytest.mark.parametrize("title", ["Senior Engineer at Acme | LinkedIn", "Acme hiring Engineer", "", "Python jobs"])
def test_split_linkedin_title_ignores_other_titles(title):
    assert extract.split_linkedin_title(title) is None


def test_linkedin_page_title_is_split_into_company_and_title(monkeypatch):
    serve(monkeypatch, linkedin_page())
    job = run(manual.job_from_url("https://www.linkedin.com/jobs/view/4462750182"))
    assert job.company == "JPMorganChase"
    assert job.title == "Applied AI ML - Associate/VP"
    assert job.location == "Greater London, England, United Kingdom"


def test_title_with_hiring_on_a_non_linkedin_site_is_left_alone(monkeypatch):
    serve(monkeypatch, linkedin_page("Acme hiring Engineer in London | LinkedIn"))
    job = run(manual.job_from_url("https://example.com/jobs/77"))
    assert job.company == ""
    assert job.title == "Acme hiring Engineer in London | LinkedIn"


def test_pasted_description_skips_fetch(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("must not fetch")

    monkeypatch.setattr(safe_fetch, "fetch_html", boom)
    job = run(
        manual.job_from_url(
            "https://www.LinkedIn.com/jobs/view/3812345678/?trk=x",
            title="Backend Dev",
            company="Initech",
            description="Fully remote role. Short pasted text.",
        )
    )
    assert job.title == "Backend Dev" and job.company == "Initech"
    assert job.description == "Fully remote role. Short pasted text."
    assert job.url == "https://www.linkedin.com/jobs/view/3812345678"
    assert job.source == "linkedin.com"
    assert job.id == job_id_for("https://www.linkedin.com/jobs/view/3812345678")
    assert job.work_mode == "remote"


def test_pasted_with_only_title_or_company_is_accepted():
    job = run(manual.job_from_url("https://example.com/j/1", title="Chef", description="Cook things."))
    assert job.title == "Chef" and job.company == ""
    job = run(manual.job_from_url("https://example.com/j/1", company="Acme", description="Cook things."))
    assert job.title == "" and job.company == "Acme"


def test_pasted_without_title_and_company_asks_for_them():
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("https://example.com/j/1", description="Some text with no names."))
    assert exc.value.needs_paste is True and "title" in exc.value.message


def test_pasted_title_company_inferred_only_when_on_page(monkeypatch):
    text = "Chef at Acme Kitchens. Cook things all day."

    async def fake_complete_json(system, user, schema, max_tokens=4000):
        return schema(title="Chef", company="Acme Kitchens")

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    job = run(manual.job_from_url("https://example.com/j/1", description=text))
    assert (job.title, job.company) == ("Chef", "Acme Kitchens")

    async def invented(system, user, schema, max_tokens=4000):
        return schema(title="CEO", company="Nowhere Inc")

    monkeypatch.setattr(llm, "complete_json", invented)
    with pytest.raises(JobLinkError):
        run(manual.job_from_url("https://example.com/j/1", description=text))


def test_pasted_path_still_validates_url():
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("ftp://example.com/j", title="a", company="b", description="c"))
    assert exc.value.needs_paste is False


def test_invalid_url_raises_before_fetch(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("must not fetch")

    monkeypatch.setattr(safe_fetch, "fetch_html", boom)
    with pytest.raises(JobLinkError) as exc:
        run(manual.job_from_url("not a url"))
    assert exc.value.needs_paste is False


def test_same_url_variants_give_same_job_id(monkeypatch):
    serve(monkeypatch, jsonld_page(POSTING))
    a = run(manual.job_from_url("https://example.com/jobs/1?utm_campaign=a#top"))
    b = run(manual.job_from_url("https://EXAMPLE.com/jobs/1/?gclid=z"))
    assert a.id == b.id
