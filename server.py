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

import os
import urllib.parse
import urllib.request

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

import geo
import render
from styles import STYLES

app = Flask(__name__)
CORS(app)

# Hosts the image proxy is allowed to fetch from (prevents SSRF).
_IMG_HOSTS = {"services.arcgisonline.com", "server.arcgisonline.com"}


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
    body = request.get_json(force=True) or {}
    prop = body.get("property")
    if not prop or not prop.get("satellite_url"):
        return jsonify({"error": "property (from /api/property) is required"}), 400
    result = render.generate(
        prop=prop,
        style_key=body.get("style", "modern"),
        vision=body.get("vision", ""),
        elements=body.get("elements"),
        time_of_day=body.get("time_of_day", "day"),
    )
    return jsonify(result)


@app.get("/api/img")
def img_proxy():
    """Allow-listed same-origin image proxy for taint-free export."""
    u = request.args.get("u", "")
    parsed = urllib.parse.urlparse(u)
    if parsed.scheme != "https" or parsed.hostname not in _IMG_HOSTS:
        return jsonify({"error": "host not allowed"}), 400
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Land-View/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "image/jpeg")
        return Response(data, mimetype=ctype,
                        headers={"Cache-Control": "public, max-age=3600"})
    except Exception as e:
        return jsonify({"error": f"fetch failed: {e}"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Land-View API on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
