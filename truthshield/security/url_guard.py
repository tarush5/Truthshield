"""
SSRF guard for user-supplied URLs.

`POST /api/v1/analyze` accepts a `url` field, hands it to URLScraper, and
returns the fetched page body back to the caller as `original_text`. Without
validation that is a full-read server-side request forgery: whatever the
server can reach, the caller can read.

Concretely, before this guard existed a caller could submit

    http://169.254.169.254/latest/meta-data/iam/security-credentials/
    http://localhost:8000/api/v1/organizations
    http://10.0.0.5:6379/

and get the response body back in the analysis report — cloud instance
credentials, internal API responses, and a working port scanner against the
private network the server sits in.

The checks here are applied at three points, because any one alone is
bypassable:

  1. Scheme — only http/https. Blocks file://, gopher://, ftp://, and the
     redirect-to-file tricks that follow from them.
  2. Resolved address — every address the hostname resolves to must be
     public. Checking the literal hostname is not enough: an attacker
     controls DNS for their own domain and can point it at 127.0.0.1
     (DNS rebinding's simpler cousin).
  3. Every redirect hop — requests follows redirects by default, so a public
     URL that 302s to the metadata endpoint defeats a check done only on the
     original URL.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}

# Hosts that are never legitimate targets even when they resolve publicly.
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
}

# Cloud instance-metadata addresses. These are inside the link-local range
# that _is_public_ip already rejects, but they are named explicitly so the
# refusal reason is legible in logs and so the list survives any future
# loosening of the range checks.
METADATA_ADDRESSES = {
    "169.254.169.254",   # AWS / Azure / DigitalOcean / Oracle
    "fd00:ec2::254",     # AWS IMDSv2 over IPv6
    "100.100.100.200",   # Alibaba Cloud
}

DEFAULT_TIMEOUT = (4.0, 8.0)   # (connect, read)
MAX_REDIRECTS = 4
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class BlockedURLError(ValueError):
    """Raised when a URL may not be fetched on the server's behalf."""


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    """
    True only for addresses that are routable on the public internet.

    `is_global` alone is not sufficient on every Python version for all the
    ranges we care about, so the specific categories are spelled out.
    """
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or getattr(ip, "is_site_local", False)
    )


def _resolved_addresses(hostname: str) -> Iterable[str]:
    """Every address `hostname` resolves to, IPv4 and IPv6."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise BlockedURLError(f"Could not resolve host: {hostname}") from exc
    return {info[4][0] for info in infos}


def assert_url_is_public(url: str) -> str:
    """
    Validate that `url` is safe for the server to fetch.

    Returns the URL unchanged when it is acceptable; raises BlockedURLError
    otherwise. The message is written to be safe to show a caller — it never
    echoes internal addresses back, since that would turn the error itself
    into the information leak the guard exists to prevent.
    """
    if not url or not url.strip():
        raise BlockedURLError("No URL provided")

    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise BlockedURLError("Only http and https URLs can be analyzed")

    hostname = (parsed.hostname or "").strip().rstrip(".").lower()
    if not hostname:
        raise BlockedURLError("URL has no host")

    if hostname in BLOCKED_HOSTNAMES:
        raise BlockedURLError("That host is not permitted")

    # A literal IP is checked directly; a name is checked against everything
    # it resolves to.
    try:
        literal = ipaddress.ip_address(hostname)
        candidates = [str(literal)]
    except ValueError:
        candidates = list(_resolved_addresses(hostname))

    if not candidates:
        raise BlockedURLError(f"Could not resolve host: {hostname}")

    for address in candidates:
        if address in METADATA_ADDRESSES:
            raise BlockedURLError("That host is not permitted")
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise BlockedURLError("That host is not permitted")
        if not _is_public_ip(ip):
            # Deliberately vague: naming the address would confirm to the
            # caller what lives on the internal network.
            raise BlockedURLError(
                "That URL points to a private or internal address, which cannot be analyzed"
            )

    return url.strip()


def safe_get(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout=DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> requests.Response:
    """
    Fetch `url` with SSRF protection and a response size cap.

    Redirects are followed manually so each hop can be validated. Letting
    requests follow them would mean only the first URL was ever checked, and a
    public URL that redirects to 169.254.169.254 would sail through.
    """
    getter = session or requests
    current = assert_url_is_public(url)

    for _ in range(MAX_REDIRECTS + 1):
        response = getter.get(
            current,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise BlockedURLError("Redirect without a destination")
            current = assert_url_is_public(requests.compat.urljoin(current, location))
            continue

        # Refuse oversized bodies by the declared length where available, and
        # by actual bytes read otherwise — Content-Length is attacker-controlled.
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            response.close()
            raise BlockedURLError("Response too large to analyze")

        content = b""
        for chunk in response.iter_content(8192):
            content += chunk
            if len(content) > max_bytes:
                response.close()
                raise BlockedURLError("Response too large to analyze")

        response._content = content
        response._content_consumed = True
        return response

    raise BlockedURLError("Too many redirects")
