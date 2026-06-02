"""Tests for SSRF protection on outbound URLs.

DNS resolution is mocked so the tests are deterministic regardless of the
host's /etc/hosts or DNS proxy.
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from app.core.ssrf import is_safe_webhook_url


# ---------------------------------------------------------------------------
# Direct IP tests (no DNS needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/admin",
        "http://127.0.0.1:8080/internal",
        "http://192.168.1.1/",
        "http://172.16.0.5/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "file:///etc/passwd",
        "gopher://example.com/",
        "ftp://example.com/",
        "",
    ],
)
def test_blocked_urls(url: str) -> None:
    safe, reason = is_safe_webhook_url(url)
    assert not safe, f"URL {url!r} should be blocked (reason={reason!r})"


@pytest.mark.parametrize(
    "url",
    [
        "https://8.8.8.8/webhook",
        "https://1.1.1.1/dns",
        "https://93.184.216.34/icanhazip",  # example.com
    ],
)
def test_public_ip_urls_allowed(url: str) -> None:
    safe, reason = is_safe_webhook_url(url)
    assert safe, f"URL {url!r} should be allowed (reason={reason!r})"


# ---------------------------------------------------------------------------
# Hostname tests (DNS mocked)
# ---------------------------------------------------------------------------


def _mock_getaddrinfo(ip: str):
    """Build a getaddrinfo return value for a given IP literal."""

    def fake(host, *args, **kwargs):
        if host == "public.example.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
        if host == "private.example.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]
        if host == "metadata.example.com":
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))
            ]
        raise socket.gaierror(-2, "Name or service not known")

    return fake


def test_hostname_resolving_to_public_ip_is_allowed() -> None:
    with patch("app.core.ssrf.socket.getaddrinfo", _mock_getaddrinfo("1.2.3.4")):
        safe, reason = is_safe_webhook_url("https://public.example.com/webhook")
    assert safe, reason


def test_hostname_resolving_to_private_ip_is_blocked() -> None:
    with patch("app.core.ssrf.socket.getaddrinfo", _mock_getaddrinfo("10.0.0.5")):
        safe, reason = is_safe_webhook_url("https://private.example.com/admin")
    assert not safe
    assert "forbidden_ip_range" in reason


def test_hostname_resolving_to_metadata_ip_is_blocked() -> None:
    with patch(
        "app.core.ssrf.socket.getaddrinfo",
        _mock_getaddrinfo("169.254.169.254"),
    ):
        safe, reason = is_safe_webhook_url("https://metadata.example.com/latest")
    assert not safe
    assert "forbidden_ip_range" in reason


# ---------------------------------------------------------------------------
# Misc edge cases
# ---------------------------------------------------------------------------


def test_empty_url_rejected() -> None:
    safe, reason = is_safe_webhook_url("")
    assert not safe
    assert reason == "empty_url"


def test_no_host_rejected() -> None:
    safe, reason = is_safe_webhook_url("https:///path")
    assert not safe
