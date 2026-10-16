from __future__ import annotations

import hashlib
import re
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

from .errors import JobLinkError

_TRACKING_KEYS = {
    "trk",
    "trkinfo",
    "trkemail",
    "trackingid",
    "refid",
    "ref",
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "lipi",
    "midtoken",
    "midsig",
    "ebp",
    "gh_src",
    "lever-source",
    "lever-origin",
    "original_referer",
}

_LINKEDIN_VIEW = re.compile(r"^/jobs/view/(?:[^/]*-)?(\d+)/?$")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def check_http_url(url: str) -> SplitResult:
    raw = (url or "").strip()
    if not raw:
        raise JobLinkError("Enter a job link.", needs_paste=False)
    try:
        parts = urlsplit(raw)
        parts.port
    except ValueError:
        raise JobLinkError("That does not look like a valid link.", needs_paste=False) from None
    if parts.scheme.lower() not in ("http", "https"):
        raise JobLinkError("Only http:// and https:// links are supported.", needs_paste=False)
    if not parts.hostname:
        raise JobLinkError("That does not look like a valid link.", needs_paste=False)
    return parts


def _is_linkedin(host: str) -> bool:
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def _is_indeed(host: str) -> bool:
    return host.startswith("indeed.") or ".indeed." in host


def normalize_url(url: str) -> str:
    parts = check_http_url(url)
    scheme = parts.scheme.lower()
    host = parts.hostname.rstrip(".")  # type: ignore[union-attr]
    path = parts.path or "/"
    query = parse_qsl(parts.query, keep_blank_values=False)

    if _is_linkedin(host):
        host = "www.linkedin.com"
        view = _LINKEDIN_VIEW.match(path)
        job_id = view.group(1) if view else None
        if not job_id and path.startswith("/jobs/"):
            for key, value in query:
                if key.lower() == "currentjobid" and value.isdigit():
                    job_id = value
                    break
        if job_id:
            return f"https://www.linkedin.com/jobs/view/{job_id}"

    if _is_indeed(host):
        values = {k.lower(): v for k, v in query}
        job_key = values.get("jk") or values.get("vjk")
        if job_key and path.rstrip("/") in ("/viewjob", "/jobs", "/m/viewjob", ""):
            path = "/viewjob"
            query = [("jk", job_key)]

    kept = [
        (k, v)
        for k, v in query
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_KEYS
    ]
    kept.sort()

    if path != "/":
        path = path.rstrip("/") or "/"
    netloc = f"[{host}]" if ":" in host else host
    if parts.port and parts.port != _DEFAULT_PORTS[scheme]:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((scheme, netloc, path, urlencode(kept), ""))


def job_id_for(normalized_url: str) -> str:
    return "m_" + hashlib.sha1(normalized_url.encode("utf-8")).hexdigest()[:16]


def source_for(normalized_url: str) -> str:
    host = urlsplit(normalized_url).hostname or ""
    return host[4:] if host.startswith("www.") else host
