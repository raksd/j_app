from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from .errors import JobLinkError
from .url import check_http_url

MAX_REDIRECTS = 4
TIMEOUT_SECONDS = 10.0
MAX_BODY_BYTES = 2 * 1024 * 1024
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
    "Accept-Language": "en-GB,en;q=0.9",
}

BLOCKED_MESSAGE = "That link points to a private or internal address, which is not allowed."
FETCH_FAILED_SUFFIX = " Paste the job title, company and description instead."


@dataclass
class FetchedPage:
    final_url: str
    html: str


async def _resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({info[4][0].split("%")[0] for info in infos})


def is_blocked_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def _legacy_ipv4(host: str) -> str | None:
    """Decimal, hex, octal and short IPv4 spellings (2130706433, 0x7f.1, 127.1) that the OS would accept."""
    if not re.fullmatch(r"[0-9a-fA-Fx.]+", host):
        return None
    try:
        return socket.inet_ntoa(socket.inet_aton(host))
    except OSError:
        return None


async def check_host(host: str) -> None:
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise JobLinkError(BLOCKED_MESSAGE, needs_paste=False)
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        legacy = _legacy_ipv4(host)
        if legacy:
            addresses = [legacy]
        else:
            try:
                addresses = await _resolve(host)
            except OSError:
                raise JobLinkError(
                    "Could not find that website." + FETCH_FAILED_SUFFIX, needs_paste=True
                ) from None
    if not addresses:
        raise JobLinkError("Could not find that website." + FETCH_FAILED_SUFFIX, needs_paste=True)
    if any(is_blocked_address(a) for a in addresses):
        raise JobLinkError(BLOCKED_MESSAGE, needs_paste=False)


def _too_large() -> JobLinkError:
    return JobLinkError("That page is too large to read." + FETCH_FAILED_SUFFIX, needs_paste=True)


async def _read_body(resp: httpx.Response) -> bytes:
    declared = resp.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise _too_large()
    chunks: list[bytes] = []
    size = 0
    async for chunk in resp.aiter_bytes():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


def _decode(resp: httpx.Response, body: bytes) -> str:
    encoding = resp.charset_encoding
    if not encoding:
        sniff = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.IGNORECASE)
        encoding = sniff.group(1).decode("ascii", "ignore") if sniff else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


async def _fetch(url: str, transport: httpx.AsyncBaseTransport | None) -> FetchedPage:
    current = url
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        follow_redirects=False,
        headers=HEADERS,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            parts = check_http_url(current)
            await check_host(parts.hostname or "")
            try:
                async with client.stream("GET", current) as resp:
                    if resp.status_code in _REDIRECT_STATUSES:
                        location = resp.headers.get("location")
                        if not location:
                            raise JobLinkError(
                                "The site sent an invalid redirect." + FETCH_FAILED_SUFFIX,
                                needs_paste=True,
                            )
                        current = urljoin(current, location)
                        continue
                    if resp.status_code >= 400:
                        raise JobLinkError(
                            f"The site refused the request (HTTP {resp.status_code})."
                            + FETCH_FAILED_SUFFIX,
                            needs_paste=True,
                        )
                    content_type = resp.headers.get("content-type", "").lower()
                    if "html" not in content_type:
                        raise JobLinkError(
                            "That link is not a web page." + FETCH_FAILED_SUFFIX, needs_paste=True
                        )
                    body = await _read_body(resp)
                    return FetchedPage(final_url=current, html=_decode(resp, body))
            except httpx.TimeoutException:
                raise JobLinkError(
                    "The site took too long to respond." + FETCH_FAILED_SUFFIX, needs_paste=True
                ) from None
            except httpx.HTTPError:
                raise JobLinkError(
                    "Could not reach that website." + FETCH_FAILED_SUFFIX, needs_paste=True
                ) from None
    raise JobLinkError("The link redirected too many times." + FETCH_FAILED_SUFFIX, needs_paste=True)


async def fetch_html(url: str, transport: httpx.AsyncBaseTransport | None = None) -> FetchedPage:
    try:
        return await asyncio.wait_for(_fetch(url, transport), timeout=TIMEOUT_SECONDS * 3)
    except asyncio.TimeoutError:
        raise JobLinkError(
            "The site took too long to respond." + FETCH_FAILED_SUFFIX, needs_paste=True
        ) from None
