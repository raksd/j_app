from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

from pydantic import BaseModel

from app import llm

from .errors import LOGIN_WALL_MESSAGE, JobLinkError

MIN_DESCRIPTION_CHARS = 200
_LLM_TEXT_LIMIT = 15000

_SKIP_TAGS = {"script", "style", "template", "svg"}
_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article",
    "header", "footer", "main", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd",
}  # fmt: skip

_WALL_URL = re.compile(r"/authwall|/login|/signin|/sign-in|/uas/login|/checkpoint/", re.IGNORECASE)
_WALL_TEXT = (
    "sign in to view",
    "join to view",
    "please enable javascript",
    "enable javascript to",
    "captcha",
    "verify you are human",
    "are you a robot",
    "unusual traffic",
    "log in to continue",
    "sign in to continue",
)


@dataclass
class Extracted:
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    posted_date: date | None = None
    salary: str | None = None
    remote: bool = False


@dataclass
class _Page:
    title: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    jsonld: list[str] = field(default_factory=list)
    text: str = ""
    noscript: str = ""


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self.parts: list[str] = []
        self.noscript_parts: list[str] = []
        self._skip = 0
        self._noscript = 0
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script":
            if "ld+json" in a.get("type", "").lower():
                self._in_jsonld = True
                self._jsonld_buf = []
            self._skip += 1
        elif tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == "noscript":
            self._noscript += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("meta", "br"):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            if self._in_jsonld:
                self.jsonld.append("".join(self._jsonld_buf))
                self._in_jsonld = False
            self._skip = max(0, self._skip - 1)
        elif tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag == "noscript":
            self._noscript = max(0, self._noscript - 1)
        elif tag == "title":
            self._in_title = False
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_buf.append(data)
        elif self._in_title:
            self.title_parts.append(data)
        elif self._skip:
            return
        elif self._noscript:
            self.noscript_parts.append(data)
        else:
            self.parts.append(data)


def _clean_text(text: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v\xa0]+", " ", ln).strip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _parse_page(html: str) -> _Page:
    parser = _PageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        pass
    return _Page(
        title=_clean_text(" ".join(parser.title_parts)).replace("\n", " "),
        meta=parser.meta,
        jsonld=parser.jsonld,
        text=_clean_text("".join(parser.parts)),
        noscript=_clean_text(" ".join(parser.noscript_parts)),
    )


def html_to_text(fragment: str) -> str:
    return _parse_page(fragment).text


def _text(value: object) -> str:
    if isinstance(value, str):
        unescaped = html_lib.unescape(value)
        if "<" in unescaped and ">" in unescaped:
            return html_to_text(unescaped)
        return _clean_text(unescaped)
    if isinstance(value, dict):
        return _text(value.get("name"))
    return ""


def _nodes(obj: object):
    if isinstance(obj, list):
        for item in obj:
            yield from _nodes(item)
    elif isinstance(obj, dict):
        yield obj
        yield from _nodes(obj.get("@graph"))


def _is_job_posting(node: dict) -> bool:
    raw = node.get("@type")
    types = raw if isinstance(raw, list) else [raw]
    return any(
        isinstance(t, str) and re.split(r"[/:#]", t)[-1].lower() == "jobposting" for t in types
    )


def _num(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _salary(value: object) -> str | None:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip() or None
    if not isinstance(value, dict):
        return None
    inner = value.get("value")
    low = high = single = unit = None
    if isinstance(inner, dict):
        low, high, single = inner.get("minValue"), inner.get("maxValue"), inner.get("value")
        unit = inner.get("unitText")
    else:
        single = inner
    if low not in (None, "") and high not in (None, ""):
        amount = f"{_num(low)}-{_num(high)}"
    else:
        picked = next((x for x in (single, low, high) if x not in (None, "")), None)
        amount = _num(picked) if picked is not None else ""
    if not amount:
        return None
    currency = value.get("currency") or ""
    suffix = f"per {str(unit).lower()}" if unit else ""
    return " ".join(p for p in (str(currency), amount, suffix) if p)


def _location(value: object) -> str:
    items = value if isinstance(value, list) else [value]
    found: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = _text(item)
        elif isinstance(item, dict):
            address = item.get("address", item)
            if isinstance(address, str):
                text = _text(address)
            elif isinstance(address, dict):
                bits = [
                    _text(address.get(k))
                    for k in ("addressLocality", "addressRegion", "addressCountry")
                ]
                text = ", ".join(b for b in bits if b)
            else:
                text = ""
        else:
            text = ""
        if text and text not in found:
            found.append(text)
    return "; ".join(found)


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _from_jsonld(blocks: list[str]) -> tuple[Extracted, bool]:
    for raw in blocks:
        try:
            data = json.loads(raw, strict=False)
        except ValueError:
            continue
        for node in _nodes(data):
            if not _is_job_posting(node):
                continue
            remote = str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE"
            return (
                Extracted(
                    title=_text(node.get("title")),
                    company=_text(node.get("hiringOrganization")),
                    location=_location(node.get("jobLocation")),
                    description=_text(node.get("description")),
                    posted_date=_parse_date(node.get("datePosted")),
                    salary=_salary(node.get("baseSalary")),
                    remote=remote,
                ),
                True,
            )
    return Extracted(), False


def _meta(page: _Page, *keys: str) -> str:
    for key in keys:
        value = page.meta.get(key)
        if value:
            return _text(value)
    return ""


class _LLMJob(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""


_LLM_SYSTEM = (
    "You extract job posting details from the visible text of a web page. "
    "Copy only what is written on the page. If a field is not on the page, return an empty "
    "string for it. Never infer, guess or invent anything. "
    "title: the job title. company: the hiring company. location: the job location. "
    "description: the job description text copied from the page, not summarised."
)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _on_page(value: str, haystack: str, prefix: int | None = None) -> str:
    value = value.strip()
    needle = _norm(value)
    if prefix:
        needle = needle[:prefix]
    return value if needle and needle in haystack else ""


async def _llm_extract(text: str, url: str) -> _LLMJob | None:
    try:
        return await llm.complete_json(
            _LLM_SYSTEM,
            f"Page URL: {url}\n\nPage text:\n{text[:_LLM_TEXT_LIMIT]}",
            _LLMJob,
        )
    except Exception:  # noqa: BLE001
        return None


async def infer_fields(text: str, url: str) -> _LLMJob:
    result = await _llm_extract(text, url)
    if result is None:
        return _LLMJob()
    haystack = _norm(text)
    return _LLMJob(
        title=_on_page(result.title, haystack),
        company=_on_page(result.company, haystack),
        location=_on_page(result.location, haystack),
        description=_on_page(result.description, haystack, prefix=40),
    )


def _looks_like_wall(page: _Page) -> bool:
    haystack = " ".join(
        [page.title, page.text[:3000], page.noscript, page.meta.get("description", "")]
    ).lower()
    return any(marker in haystack for marker in _WALL_TEXT)


def _wall() -> JobLinkError:
    return JobLinkError(LOGIN_WALL_MESSAGE, needs_paste=True)


_LINKEDIN_TITLE_WITH_PLACE = re.compile(
    r"^(?P<company>.+?)\s+hiring\s+(?P<title>.+)\s+in\s+(?P<location>.+?)\s*\|\s*LinkedIn\s*$", re.IGNORECASE
)
_LINKEDIN_TITLE = re.compile(r"^(?P<company>.+?)\s+hiring\s+(?P<title>.+?)\s*\|\s*LinkedIn\s*$", re.IGNORECASE)


def split_linkedin_title(page_title: str) -> tuple[str, str, str] | None:
    """LinkedIn page titles read '<Company> hiring <Title> in <Location> | LinkedIn'."""
    text = re.sub(r"\s+", " ", page_title or "").strip()
    match = _LINKEDIN_TITLE_WITH_PLACE.match(text) or _LINKEDIN_TITLE.match(text)
    if not match:
        return None
    parts = match.groupdict(default="")
    return parts["company"].strip(), parts["title"].strip(), parts.get("location", "").strip()


def _is_linkedin(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


async def extract_job(html: str, final_url: str) -> Extracted:
    if _WALL_URL.search(urlsplit(final_url).path):
        raise _wall()
    page = _parse_page(html)
    data, from_ld = _from_jsonld(page.jsonld)
    if not (from_ld and len(data.description) >= MIN_DESCRIPTION_CHARS) and _looks_like_wall(page):
        raise _wall()

    title_from_ld = bool(data.title)
    desc_from_ld = bool(data.description)
    if not data.title:
        data.title = _meta(page, "og:title", "twitter:title") or _text(page.title)
        split = split_linkedin_title(data.title) if _is_linkedin(final_url) else None
        if split:
            company, data.title, location = split
            data.company = data.company or company
            data.location = data.location or location
    meta_desc = _meta(page, "og:description", "twitter:description", "description")
    if len(meta_desc) > len(data.description):
        data.description = meta_desc

    if not (data.title and data.company) or len(data.description) < MIN_DESCRIPTION_CHARS:
        found = await infer_fields(page.text, final_url)
        if found.title and not title_from_ld:
            data.title = found.title
        if found.company and not data.company:
            data.company = found.company
        if found.location and not data.location:
            data.location = found.location
        if found.description and len(found.description) > len(data.description):
            if not desc_from_ld or len(data.description) < MIN_DESCRIPTION_CHARS:
                data.description = found.description

    if len(data.description) < MIN_DESCRIPTION_CHARS and data.title and len(page.text) >= MIN_DESCRIPTION_CHARS:
        data.description = page.text[:_LLM_TEXT_LIMIT]
    if len(data.description) < MIN_DESCRIPTION_CHARS:
        raise _wall()
    if not data.title:
        raise JobLinkError(
            "Could not find the job title on this page. "
            "Paste the job title, company and description instead.",
            needs_paste=True,
        )
    return data


_NEGATED_REMOTE = re.compile(r"\b(?:no|not|non|without)[\s-]+(?:fully[\s-]+)?remote(?:ly)?\b")
_NEGATED_ONSITE = re.compile(r"\b(?:no|not|non|without)[\s-]+on[\s-]?site\b")
_HYBRID = re.compile(r"\bhybrid\b")
_REMOTE = re.compile(
    r"\bremote(?:ly|[\s-]first|[\s-]friendly)?\b|\bwork(?:ing)?\s+from\s+home\b|\bwfh\b"
)
_ONSITE = re.compile(r"\bon[\s-]?site\b|\bin[\s-]?office\b|\bin\s+the\s+office\b|\boffice[\s-]?based\b")


def infer_work_mode(text: str, remote_flag: bool = False) -> str:
    lowered = (text or "").lower()
    if _HYBRID.search(lowered):
        return "hybrid"
    if remote_flag:
        return "remote"
    remote = bool(_REMOTE.search(_NEGATED_REMOTE.sub(" ", lowered)))
    onsite = bool(_ONSITE.search(_NEGATED_ONSITE.sub(" ", lowered)))
    if remote and onsite:
        return "unknown"
    if remote:
        return "remote"
    if onsite:
        return "onsite"
    return "unknown"
