"""Async URL fetcher with SSRF defense for document ingestion.

Performs strict validation of remote URLs before fetching:
- Scheme must be http/https
- Hostname is resolved at validation time AND on every redirect; resolved IPs
  must not be private, loopback, link-local, multicast, reserved, or the
  cloud-metadata range (169.254.169.254, fd00:ec2::254, etc.)
- Response Content-Type must be on the allowlist (missing types rejected)
- Response size capped via streaming with a hard byte limit
- Redirects manually followed with re-validation each hop (prevents
  open-redirect → internal-IP and DNS-rebinding-on-redirect attacks)

Residual risks:
- DNS rebinding TOCTOU: between validate_url() and the actual connect, a
  malicious DNS server with low TTL could swap to a private IP. The kernel
  resolver caches this in practice; deployments that need stronger isolation
  should run the worker in a network namespace that blocks RFC1918 egress.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx

from src.core.settings import Settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})

# MIME prefixes Docling can convert (we strip parameters before matching).
ALLOWED_MIME_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        "text/markdown",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)

# Cloud / orchestrator metadata endpoints. urllib's `is_private` already covers
# 169.254.0.0/16 (link-local) which contains AWS/GCP/Azure IMDS, but we keep an
# explicit list here for defense-in-depth and clearer error logging.
BLOCKED_METADATA_HOSTS = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure / DigitalOcean / Alibaba
        "fd00:ec2::254",  # AWS IMDSv6
        "100.100.100.200",  # Alibaba
        "metadata.google.internal",
        "metadata.goog",
    }
)

DEFAULT_USER_AGENT = "MongoRAG-URLIngester/1.0 (+https://mongorag.com)"


class URLValidationError(ValueError):
    """Raised when a URL fails security validation (SSRF, scheme, etc.)."""


class URLFetchError(RuntimeError):
    """Raised when a URL cannot be fetched (network, size, MIME, status)."""


@dataclass(frozen=True)
class FetchedURL:
    """Result of a successful URL fetch."""

    url: str  # Originally requested URL
    final_url: str  # Final URL after redirects
    content: bytes
    content_type: str  # Bare media type, e.g. "text/html"
    charset: Optional[str]
    title: Optional[str] = None


def _normalize_mime(content_type: str) -> tuple[str, Optional[str]]:
    """Split a Content-Type header into (media_type, charset)."""
    if not content_type:
        return ("", None)
    parts = [p.strip() for p in content_type.split(";")]
    media = parts[0].lower()
    charset: Optional[str] = None
    for p in parts[1:]:
        if p.lower().startswith("charset="):
            charset = p.split("=", 1)[1].strip().strip("\"'") or None
    return (media, charset)


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    """Block private, loopback, link-local, multicast, reserved, unspecified."""
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_and_check_host(host: str, *, allow_private: bool) -> list[str]:
    """Resolve a hostname and ensure NO resolved IP is in a blocked range.

    Returns the list of resolved IP strings on success.
    Raises URLValidationError if any IP is blocked or resolution fails.

    Note: All resolved addresses are checked. This thwarts DNS-rebinding-style
    tricks where a hostname resolves to one public + one private address.
    """
    if host in BLOCKED_METADATA_HOSTS:
        raise URLValidationError(f"Host '{host}' is blocked (metadata endpoint)")

    # Reject literal IPs that are blocked (skipping the DNS round-trip).
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not allow_private and _is_blocked_ip(literal):
            raise URLValidationError(
                f"IP address '{host}' is in a blocked range (private/loopback/link-local)"
            )
        return [str(literal)]

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise URLValidationError(f"DNS lookup failed for '{host}'") from e

    resolved: list[str] = []
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if not allow_private and _is_blocked_ip(ip):
            raise URLValidationError(f"Host '{host}' resolved to blocked IP '{ip_str}'")
        resolved.append(ip_str)

    if not resolved:
        raise URLValidationError(f"DNS resolution returned no usable addresses for '{host}'")
    return resolved


def validate_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a URL is safe to fetch.

    Args:
        url: User-supplied URL.
        allow_private: If True, skip private-IP checks (test-only).

    Returns:
        The normalized URL string.

    Raises:
        URLValidationError: If the URL fails any safety check.
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL is required")

    if len(url) > 2048:
        raise URLValidationError("URL is too long (max 2048 chars)")

    try:
        parsed = urlparse(url.strip())
    except (ValueError, TypeError) as e:
        raise URLValidationError("Malformed URL") from e

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise URLValidationError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    host = parsed.hostname
    if not host:
        raise URLValidationError("URL is missing a hostname")

    # Defence: refuse credentials in URL (avoid leaking via logs / proxies).
    if parsed.username or parsed.password:
        raise URLValidationError("URLs with embedded credentials are not allowed")

    _resolve_and_check_host(host, allow_private=allow_private)
    return urlunparse(parsed)


async def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    """Stream a response, aborting if it exceeds max_bytes."""
    buf = bytearray()
    async for chunk in response.aiter_bytes():
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise URLFetchError(f"Response exceeds maximum size of {max_bytes} bytes")
    return bytes(buf)


async def fetch_url(
    url: str,
    settings: Settings,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> FetchedURL:
    """Fetch a URL with SSRF protection, size cap, and MIME allowlist.

    Manually follows up to ``settings.url_fetch_max_redirects`` redirects,
    re-validating each Location to defeat redirect-based SSRF.

    Args:
        url: URL to fetch.
        settings: App settings.
        client: Optional pre-built httpx.AsyncClient (used in tests).

    Returns:
        FetchedURL with raw bytes and detected content type.

    Raises:
        URLValidationError: If URL or any redirect target fails safety checks.
        URLFetchError: For network/HTTP/size errors.
    """
    allow_private = settings.url_fetch_allow_private_ips
    max_bytes = settings.url_fetch_max_size_mb * 1024 * 1024
    max_redirects = max(0, int(settings.url_fetch_max_redirects))
    timeout = httpx.Timeout(settings.url_fetch_timeout_seconds, connect=10.0)

    current = validate_url(url, allow_private=allow_private)

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "*/*"},
            max_redirects=0,
        )

    try:
        for hop in range(max_redirects + 1):
            try:
                async with client.stream("GET", current) as response:
                    # Redirect handling — re-validate target.
                    if response.is_redirect:
                        if hop >= max_redirects:
                            raise URLFetchError(f"Too many redirects (max {max_redirects})")
                        location = response.headers.get("location")
                        if not location:
                            raise URLFetchError("Redirect without Location header")
                        # Resolve relative locations against the current URL.
                        next_url = str(httpx.URL(current).join(location))
                        current = validate_url(next_url, allow_private=allow_private)
                        # Drain & continue to next hop.
                        await response.aclose()
                        continue

                    if response.status_code >= 400:
                        raise URLFetchError(f"Upstream returned HTTP {response.status_code}")

                    # Cheap pre-flight using Content-Length when available.
                    declared_len = response.headers.get("content-length")
                    if declared_len and declared_len.isdigit() and int(declared_len) > max_bytes:
                        raise URLFetchError(f"Response exceeds maximum size of {max_bytes} bytes")

                    media_type, charset = _normalize_mime(response.headers.get("content-type", ""))
                    # Reject responses with no Content-Type or a type not on
                    # the allowlist. An unset header is suspicious and lets a
                    # server smuggle binary/executable content past us.
                    if not media_type or media_type not in ALLOWED_MIME_TYPES:
                        raise URLFetchError(f"Unsupported or missing content type '{media_type}'")

                    body = await _read_capped(response, max_bytes)
                    if not body:
                        raise URLFetchError("Empty response body")

                    return FetchedURL(
                        url=url,
                        final_url=current,
                        content=body,
                        content_type=media_type or "application/octet-stream",
                        charset=charset,
                    )
            except httpx.TimeoutException as e:
                raise URLFetchError("Request timed out") from e
            except httpx.RequestError as e:
                # Network-level error (connect refused, TLS, etc.). Surface a
                # generic message — don't leak internal infrastructure details.
                logger.warning("URL fetch network error for %s: %s", current, e)
                raise URLFetchError("Network error fetching URL") from e

        raise URLFetchError(f"Too many redirects (max {max_redirects})")
    finally:
        if owns_client and client is not None:
            await client.aclose()


def html_to_markdown(content: bytes, charset: Optional[str] = None) -> str:
    """Best-effort HTML→markdown fallback used when Docling cannot convert.

    Strips scripts/styles, drops tags, collapses whitespace. Output is plain
    text wrapped in a minimal structure that preserves line breaks; it is fed
    through the same chunker pipeline.
    """
    import html
    import re

    if not content:
        return ""

    encoding = charset or "utf-8"
    try:
        text = content.decode(encoding, errors="replace")
    except (LookupError, TypeError):
        text = content.decode("utf-8", errors="replace")

    # Strip script/style/noscript blocks first (case-insensitive, multiline).
    text = re.sub(
        r"<(script|style|noscript|template)\b[^>]*>.*?</\1>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Convert paragraph/line-break tags to explicit newlines.
    text = re.sub(r"</(p|div|section|article|li|h[1-6]|tr|br)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Drop remaining tags.
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode entities.
    text = html.unescape(text)
    # Collapse runs of whitespace per line, then trim blank lines.
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned
