from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_loopback_url(url: str) -> bool:
    """Return whether a URL points to localhost or a loopback IP."""

    host = urlparse(url).hostname
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
