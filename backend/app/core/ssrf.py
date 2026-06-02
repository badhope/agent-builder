"""SSRF (Server-Side Request Forgery) defense helpers for outbound HTTP.

Used by the webhook delivery service to refuse URLs that target private
networks, link-local addresses, AWS / GCP / Azure metadata services, or
non-HTTP(S) schemes (CWE-918).

Typical attack:
    Attacker registers webhook URL = http://169.254.169.254/latest/meta-data/iam/security-credentials/
    → server-side GET reads cloud instance role credentials.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Private / link-local / loopback / multicast / cloud-metadata ranges that
# must NEVER be reached by an outbound webhook delivery.
_FORBIDDEN_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),       # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),      # link-local + AWS/GCP/Azure metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::ffff:0:0/96"),       # IPv4-mapped
    ipaddress.ip_network("fc00::/7"),            # ULA
    ipaddress.ip_network("fe80::/10"),           # link-local
    ipaddress.ip_network("ff00::/8"),            # multicast
]

# Allow-list of schemes for webhook delivery.
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class SSRFError(ValueError):
    """Raised when an outbound URL targets a forbidden destination."""


def is_safe_webhook_url(url: str) -> tuple[bool, str | None]:
    """Validate that ``url`` is safe for server-side delivery.

    Returns ``(True, None)`` if the URL is acceptable, otherwise
    ``(False, reason)`` describing why it was rejected.
    """
    if not url:
        return False, "empty_url"
    try:
        parsed = urlparse(url)
    except Exception as exc:  # noqa: BLE001
        return False, f"parse_error:{exc}"

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, f"scheme_not_allowed:{parsed.scheme}"
    if not parsed.hostname:
        return False, "no_host"

    # Resolve all IPs that the hostname maps to and verify each one.
    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        return False, f"dns_resolution_failed:{exc}"

    seen: set[str] = set()
    for family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if ip_str in seen:
            continue
        seen.add(ip_str)
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"invalid_ip:{ip_str}"
        for net in _FORBIDDEN_NETWORKS:
            if ip in net:
                return False, f"forbidden_ip_range:{net}"

    return True, None


__all__ = ["is_safe_webhook_url", "SSRFError"]
