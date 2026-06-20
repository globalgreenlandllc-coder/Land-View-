"""
netfetch.py -- The single hardened image fetcher, shared by the API proxy and the
render providers so every server-side image fetch gets the same SSRF protections:
https-only + host allow-list + public-IP DNS check + no redirect following + a
size cap + Content-Type check.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request

# Hosts any server-side image fetch may reach. Add render-provider/CDN hosts here
# (not an open fetch) when enabling live renders that return URLs.
IMG_HOSTS = {"services.arcgisonline.com", "server.arcgisonline.com"}
MAX_IMG_BYTES = 12 * 1024 * 1024


def is_allowed_image_url(u: str) -> bool:
    """https + host on the allow-list + the resolved IP is public (anti-SSRF)."""
    try:
        p = urllib.parse.urlparse(u)
    except ValueError:
        return False
    if p.scheme != "https" or p.hostname not in IMG_HOSTS:
        return False
    try:
        for info in socket.getaddrinfo(p.hostname, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # block redirect-based allow-list bypass
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def safe_image_fetch(u: str):
    """Fetch an allow-listed image with no redirects + a size cap. Returns (bytes, ctype)."""
    if not is_allowed_image_url(u):
        raise ValueError("image host not allowed")
    req = urllib.request.Request(u, headers={"User-Agent": "Land-View/1.0"})
    with _opener.open(req, timeout=20) as r:
        ctype = r.headers.get("Content-Type", "image/jpeg")
        if not ctype.startswith("image/"):
            raise ValueError("not an image")
        data = r.read(MAX_IMG_BYTES + 1)
    if len(data) > MAX_IMG_BYTES:
        raise ValueError("image too large")
    return data, ctype
