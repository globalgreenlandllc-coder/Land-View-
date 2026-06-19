"""
server.py -- Land-View backend (Phase 1).

Endpoints:
  GET  /api/health
  GET  /api/styles               -> style presets
  GET  /api/property?q=ADDRESS    -> geocode + satellite + estimated sizes
  POST /api/render                -> engineered prompt + render (demo unless a
                                     RENDER_PROVIDER + key is configured)
  GET  /api/img?u=URL             -> same-origin image proxy (allow-listed hosts)
                                     so the client can export renders without
                                     tainting the canvas.

Run:  python server.py            (http://localhost:8000)
"""
from __future__ import annotations

import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

import geo
import render
from styles import STYLES

app = Flask(__name__)
# Scope CORS to the local dev origins instead of "*".
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5173", "http://127.0.0.1:5173",
]}})

# Hosts any server-side image fetch is allowed to reach (prevents SSRF). Image
# generation conditions on these, and the proxy only serves these.
_IMG_HOSTS = {"services.arcgisonline.com", "server.arcgisonline.com"}
_MAX_IMG_BYTES = 12 * 1024 * 1024


def is_allowed_image_url(u: str) -> bool:
    """https + host on the allow-list + the resolved IP is public (anti-SSRF)."""
    try:
        p = urllib.parse.urlparse(u)
    except ValueError:
        return False
    if p.scheme != "https" or p.hostname not in _IMG_HOSTS:
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


_no_redirect_opener = urllib.request.build_opener(_NoRedirect)


def safe_image_fetch(u: str):
    """Fetch an allow-listed image with no redirects + a size cap. (bytes, ctype)."""
    if not is_allowed_image_url(u):
        raise ValueError("image host not allowed")
    req = urllib.request.Request(u, headers={"User-Agent": "Land-View/1.0"})
    with _no_redirect_opener.open(req, timeout=20) as r:
        ctype = r.headers.get("Content-Type", "image/jpeg")
        if not ctype.startswith("image/"):
            raise ValueError("not an image")
        data = r.read(_MAX_IMG_BYTES + 1)
    if len(data) > _MAX_IMG_BYTES:
        raise ValueError("image too large")
    return data, ctype


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/styles")
def styles():
    return jsonify({"styles": [
        {k: s[k] for k in ("key", "name", "blurb", "palette")} for s in STYLES
    ]})


@app.get("/api/property")
def property_endpoint():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "address (q) required"}), 400
    try:
        return jsonify(geo.property_intake(q))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"property lookup failed: {e}"}), 502


@app.post("/api/render")
def render_endpoint():
    try:
        body = request.get_json(force=True, silent=True) or {}
    except Exception:
        return jsonify({"error": "invalid JSON body"}), 400
    prop = body.get("property")
    if not isinstance(prop, dict) or not prop.get("satellite_url"):
        return jsonify({"error": "property (from /api/property) is required"}), 400
    # Anti-SSRF: the satellite_url is conditioned on / fetched server-side, so it
    # must be one of our allow-listed image hosts — not an arbitrary client URL.
    if not is_allowed_image_url(prop["satellite_url"]):
        return jsonify({"error": "property.satellite_url is not an allowed image URL"}), 400

    elements = body.get("elements")
    if elements is not None and not isinstance(elements, list):
        return jsonify({"error": "elements must be a list"}), 400
    try:
        result = render.generate(
            prop=prop,
            style_key=str(body.get("style", "modern")),
            vision=str(body.get("vision", "") or ""),
            elements=elements,
            time_of_day=str(body.get("time_of_day", "day")),
        )
    except Exception:
        app.logger.exception("render failed")
        return jsonify({"error": "render failed"}), 500
    return jsonify(result)


@app.get("/api/img")
def img_proxy():
    """Allow-listed same-origin image proxy for taint-free export."""
    u = request.args.get("u", "")
    if not is_allowed_image_url(u):
        return jsonify({"error": "host not allowed"}), 400
    try:
        data, ctype = safe_image_fetch(u)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (urllib.error.URLError, socket.timeout, OSError):
        return jsonify({"error": "upstream fetch failed"}), 502
    return Response(data, mimetype=ctype,
                    headers={"Cache-Control": "public, max-age=3600"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # Default host 0.0.0.0 so a phone on the same wifi can reach it on-site; set
    # HOST=127.0.0.1 to restrict. Debug is off unless DEBUG=1 (never on in prod).
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("DEBUG", "0") == "1"
    print(f"Land-View API on http://localhost:{port} (host={host}, debug={debug})")
    app.run(host=host, port=port, debug=debug)
