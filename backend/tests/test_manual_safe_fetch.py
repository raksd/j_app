import asyncio

import httpx
import pytest

from app.services.manual import JobLinkError
from app.services.manual import safe_fetch

PUBLIC_IP = "93.184.216.34"
HTML = "<html><body><p>Hello job</p></body></html>"


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    table = {
        "example.com": [PUBLIC_IP],
        "internal.example.com": ["10.1.2.3"],
        "linklocal.example.com": ["169.254.169.254"],
        "v6.example.com": ["::1"],
        "mixed.example.com": [PUBLIC_IP, "192.168.0.5"],
        "mapped.example.com": ["::ffff:127.0.0.1"],
    }

    async def resolve(host):
        if host not in table:
            raise OSError("no such host")
        return table[host]

    monkeypatch.setattr(safe_fetch, "_resolve", resolve)


def fetch(url, handler):
    return asyncio.run(safe_fetch.fetch_html(url, transport=httpx.MockTransport(handler)))


def never_called(request):
    raise AssertionError("request must not be sent")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://127.1.2.3/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fc00::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        "http://224.0.0.1/",
        "http://2130706433/",
        "http://localhost/",
        "http://app.localhost/",
        "http://internal.example.com/",
        "http://linklocal.example.com/",
        "http://v6.example.com/",
        "http://mixed.example.com/",
        "http://mapped.example.com/",
    ],
)
def test_blocked_addresses_are_rejected_without_a_request(url):
    with pytest.raises(JobLinkError) as exc:
        fetch(url, never_called)
    assert exc.value.needs_paste is False


@pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "gopher://example.com"])
def test_non_http_schemes_rejected(url):
    with pytest.raises(JobLinkError) as exc:
        fetch(url, never_called)
    assert exc.value.needs_paste is False


def test_redirect_to_private_address_is_rejected():
    def handler(request):
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://10.0.0.1/secret"})
        raise AssertionError("private host must not be requested")

    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/job", handler)
    assert exc.value.needs_paste is False


def test_redirect_to_host_resolving_private_is_rejected():
    def handler(request):
        if request.url.host == "example.com":
            return httpx.Response(301, headers={"location": "https://internal.example.com/x"})
        raise AssertionError("private host must not be requested")

    with pytest.raises(JobLinkError):
        fetch("https://example.com/job", handler)


def test_redirect_to_non_http_scheme_is_rejected():
    def handler(request):
        return httpx.Response(302, headers={"location": "file:///etc/passwd"})

    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/job", handler)
    assert exc.value.needs_paste is False


def test_follows_relative_redirects_and_returns_final_url():
    def handler(request):
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": "/b"})
        return httpx.Response(200, html=HTML)

    page = fetch("https://example.com/a", handler)
    assert page.final_url == "https://example.com/b"
    assert "Hello job" in page.html


def test_four_redirects_allowed_five_rejected():
    def make(total):
        def handler(request):
            n = int(request.url.path.strip("/") or 0)
            if n < total:
                return httpx.Response(302, headers={"location": f"/{n + 1}"})
            return httpx.Response(200, html=HTML)

        return handler

    assert fetch("https://example.com/0", make(4)).final_url.endswith("/4")
    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/0", make(5))
    assert exc.value.needs_paste is True


def test_unknown_host_needs_paste():
    with pytest.raises(JobLinkError) as exc:
        fetch("https://nope.invalid/", never_called)
    assert exc.value.needs_paste is True


def test_non_html_rejected():
    def handler(request):
        return httpx.Response(200, json={"a": 1})

    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/", handler)
    assert exc.value.needs_paste is True


def test_http_error_status():
    def handler(request):
        return httpx.Response(403, html="denied")

    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/", handler)
    assert "403" in exc.value.message and exc.value.needs_paste is True


def test_oversized_body_rejected():
    big = "<html>" + "a" * (safe_fetch.MAX_BODY_BYTES + 10) + "</html>"

    def handler(request):
        return httpx.Response(200, html=big)

    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/", handler)
    assert "too large" in exc.value.message


def test_declared_content_length_too_large():
    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": str(safe_fetch.MAX_BODY_BYTES + 1)},
            content=b"x",
        )

    with pytest.raises((JobLinkError, httpx.HTTPError)):
        fetch("https://example.com/", handler)


def test_timeout_and_network_errors_map_to_job_link_error():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def broken(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/", timeout)
    assert exc.value.needs_paste is True
    with pytest.raises(JobLinkError) as exc:
        fetch("https://example.com/", broken)
    assert exc.value.needs_paste is True


def test_sends_browser_user_agent_and_no_cookies():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, html=HTML)

    fetch("https://example.com/", handler)
    assert seen["user-agent"].startswith("Mozilla/5.0")
    assert "cookie" not in seen
    assert "authorization" not in seen


def test_blocked_address_helper():
    assert safe_fetch.is_blocked_address("127.0.0.1")
    assert safe_fetch.is_blocked_address("::1")
    assert safe_fetch.is_blocked_address("100.64.0.1")
    assert safe_fetch.is_blocked_address("240.0.0.1")
    assert not safe_fetch.is_blocked_address(PUBLIC_IP)
    assert not safe_fetch.is_blocked_address("2606:4700:4700::1111")
