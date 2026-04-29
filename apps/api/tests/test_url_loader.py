"""Unit tests for URL loader: SSRF defense, MIME allowlist, size guard.

These tests exercise validate_url() against the IP/host blocklists and
fetch_url() against a fake httpx transport so they run with no network access.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from src.core.settings import Settings
from src.services.ingestion.url_loader import (
    URLFetchError,
    URLValidationError,
    fetch_url,
    html_to_markdown,
    validate_url,
)


def _settings(**overrides) -> Settings:
    """Build a Settings instance with safe test defaults."""
    base = {
        "mongodb_uri": "mongodb://localhost:27017/test",
        "llm_api_key": "x",
        "embedding_api_key": "x",
        "nextauth_secret": "test-secret-for-unit-tests-minimum-32chars",
        "url_fetch_timeout_seconds": 5.0,
        "url_fetch_max_redirects": 3,
        "url_fetch_max_size_mb": 1,
        "url_fetch_allow_private_ips": False,
    }
    base.update(overrides)
    return Settings(**base)


# --- validate_url ---------------------------------------------------------


@pytest.mark.unit
def test_validate_url_rejects_non_http_schemes():
    """file://, ftp://, gopher://, javascript: must be rejected."""
    for bad in [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com",
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
    ]:
        with pytest.raises(URLValidationError):
            validate_url(bad)


@pytest.mark.unit
def test_validate_url_rejects_credentials_in_url():
    """URLs with embedded basic-auth must be rejected."""
    with pytest.raises(URLValidationError):
        validate_url("https://user:pass@example.com/")


@pytest.mark.unit
def test_validate_url_rejects_loopback_literal():
    with pytest.raises(URLValidationError):
        validate_url("http://127.0.0.1/")


@pytest.mark.unit
def test_validate_url_rejects_localhost_resolving_to_loopback():
    """`localhost` typically resolves to 127.0.0.1 — must be blocked."""
    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("127.0.0.1", 0))],
    ):
        with pytest.raises(URLValidationError):
            validate_url("http://localhost/")


@pytest.mark.unit
def test_validate_url_rejects_private_rfc1918():
    for ip in ["10.0.0.1", "192.168.1.1", "172.16.5.5"]:
        with pytest.raises(URLValidationError):
            validate_url(f"http://{ip}/")


@pytest.mark.unit
def test_validate_url_rejects_link_local_and_metadata():
    """169.254.0.0/16 covers AWS/GCP/Azure metadata + the explicit blocklist."""
    with pytest.raises(URLValidationError):
        validate_url("http://169.254.169.254/")
    with pytest.raises(URLValidationError):
        validate_url("http://metadata.google.internal/")


@pytest.mark.unit
def test_validate_url_rejects_ipv6_loopback():
    with pytest.raises(URLValidationError):
        validate_url("http://[::1]/")


@pytest.mark.unit
def test_validate_url_rejects_ipv6_link_local():
    with pytest.raises(URLValidationError):
        validate_url("http://[fe80::1]/")


@pytest.mark.unit
def test_validate_url_rejects_dns_rebind_mixed_resolution():
    """If a hostname resolves to one public + one private IP, reject it."""
    addrs = [
        (2, 1, 6, "", ("203.0.113.10", 0)),  # public
        (2, 1, 6, "", ("10.0.0.5", 0)),  # private — must trigger reject
    ]
    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=addrs,
    ):
        with pytest.raises(URLValidationError):
            validate_url("http://rebound.example.com/")


@pytest.mark.unit
def test_validate_url_accepts_public_ip():
    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        out = validate_url("https://example.com/page")
        assert out.startswith("https://example.com")


@pytest.mark.unit
def test_validate_url_rejects_oversized_url():
    long_url = "https://example.com/" + ("a" * 5000)
    with pytest.raises(URLValidationError):
        validate_url(long_url)


# --- html_to_markdown -----------------------------------------------------


@pytest.mark.unit
def test_html_to_markdown_strips_scripts_and_styles():
    html = b"""<html><head><style>body{}</style><script>alert(1)</script></head>
    <body><h1>Hello</h1><p>World</p></body></html>"""
    out = html_to_markdown(html)
    assert "alert" not in out
    assert "Hello" in out
    assert "World" in out


@pytest.mark.unit
def test_html_to_markdown_handles_invalid_charset():
    out = html_to_markdown(b"<p>hi</p>", charset="not-a-real-encoding")
    assert "hi" in out


# --- fetch_url ------------------------------------------------------------


def _make_client(handler) -> httpx.AsyncClient:
    """Wrap a request handler in an httpx AsyncClient using MockTransport."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,
        timeout=httpx.Timeout(5.0),
        max_redirects=0,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_returns_body_for_allowed_mime():
    body = b"<html><body><h1>Hi</h1></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/html; charset=utf-8"}
        )

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        result = await fetch_url("https://example.com/", _settings(), client=client)
        await client.aclose()

    assert result.content == body
    assert result.content_type == "text/html"
    assert result.charset == "utf-8"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_rejects_disallowed_mime():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"binary", headers={"content-type": "application/x-msdownload"}
        )

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLFetchError):
            await fetch_url("https://example.com/x", _settings(), client=client)
        await client.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_rejects_missing_content_type():
    """Server with no Content-Type header is suspicious — reject."""

    def handler(request: httpx.Request) -> httpx.Response:
        # httpx auto-sets content-type when content is given, so override.
        return httpx.Response(200, content=b"<p>hi</p>", headers={"content-type": ""})

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLFetchError):
            await fetch_url("https://example.com/", _settings(), client=client)
        await client.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_rejects_oversized_via_content_length():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 100,
            headers={
                "content-type": "text/html",
                "content-length": str(50 * 1024 * 1024),
            },
        )

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLFetchError):
            await fetch_url("https://example.com/", _settings(), client=client)
        await client.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_rejects_oversized_via_streaming():
    """Server lies (no content-length) but body exceeds the cap mid-stream."""
    big = b"x" * (2 * 1024 * 1024)  # 2MB; cap is 1MB per _settings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=big, headers={"content-type": "text/html"})

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLFetchError):
            await fetch_url("https://example.com/", _settings(), client=client)
        await client.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_redirect_to_private_ip_blocked():
    """Open-redirect → 127.0.0.1 must be rejected on the redirect hop."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        return httpx.Response(200, content=b"secret", headers={"content-type": "text/html"})

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLValidationError):
            await fetch_url("https://example.com/", _settings(), client=client)
        await client.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_too_many_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.com/next"})

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLFetchError):
            await fetch_url(
                "https://example.com/", _settings(url_fetch_max_redirects=2), client=client
            )
        await client.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_url_propagates_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"err", headers={"content-type": "text/html"})

    with patch(
        "src.services.ingestion.url_loader.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        client = _make_client(handler)
        with pytest.raises(URLFetchError):
            await fetch_url("https://example.com/", _settings(), client=client)
        await client.aclose()
