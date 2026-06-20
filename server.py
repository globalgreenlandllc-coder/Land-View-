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

import base64
import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

def _load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines from a local .env (so API keys never live in code/chat)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()  # must run before render reads provider/key env vars

import cost as cost_mod
import geo
import pdf as pdf_mod
import render
import store as designs
from elements import ELEMENTS
from styles import STYLES

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # cap request bodies at 4 MB
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
    return jsonify({"ok": True, "render": render.render_status()})


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
        result["cost"] = cost_mod.estimate(elements or [], prop.get("sizes"))
    except Exception:
        app.logger.exception("render failed")
        return jsonify({"error": "render failed"}), 500
    return jsonify(result)


# ---------------------------------------------------------------------------
# Elements catalog + cost
# ---------------------------------------------------------------------------

@app.get("/api/elements")
def elements_catalog():
    return jsonify({"elements": ELEMENTS})


@app.post("/api/cost")
def cost_endpoint():
    body = request.get_json(force=True, silent=True) or {}
    els = body.get("elements")
    if els is not None and not isinstance(els, list):
        return jsonify({"error": "elements must be a list"}), 400
    try:
        return jsonify(cost_mod.estimate(els or [], body.get("sizes")))
    except Exception:
        app.logger.exception("cost failed")
        return jsonify({"error": "invalid input"}), 400


# ---------------------------------------------------------------------------
# Saved designs
# ---------------------------------------------------------------------------

@app.get("/api/designs")
def designs_index():
    return jsonify({"designs": designs.list_designs()})


@app.post("/api/designs")
def designs_save():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(designs.save_design(body))


@app.get("/api/designs/<did>")
def designs_get(did):
    d = designs.get_design(did)
    return (jsonify(d), 200) if d else (jsonify({"error": "not found"}), 404)


@app.delete("/api/designs/<did>")
def designs_delete(did):
    return jsonify({"ok": designs.delete_design(did)})


# ---------------------------------------------------------------------------
# PDF client presentation
# ---------------------------------------------------------------------------

def _resolve_image_bytes(u: str):
    if not u:
        return None
    if u.startswith("data:"):
        try:
            return base64.b64decode(u.split(",", 1)[1])
        except Exception:
            return None
    if is_allowed_image_url(u):
        try:
            return safe_image_fetch(u)[0]
        except Exception:
            return None
    # Anything else (arbitrary client-supplied URL) is NOT fetched — that would be
    # SSRF. Real provider renders arrive as data: URLs, or add the provider host to
    # the image allow-list to enable them here safely.
    return None


@app.post("/api/pdf")
def pdf_endpoint():
    body = request.get_json(force=True, silent=True) or {}
    prop = body.get("property") or {}
    elements = body.get("elements") or []
    design = {
        "address": body.get("address") or prop.get("address", ""),
        "style": body.get("style", "modern"),
        "vision": body.get("vision", ""),
        "elements": elements,
        "time_of_day": body.get("time_of_day", "day"),
    }
    cost = cost_mod.estimate(elements, prop.get("sizes"))
    before = _resolve_image_bytes(prop.get("satellite_url"))
    after = _resolve_image_bytes(body.get("after_url") or prop.get("satellite_url"))
    try:
        data = pdf_mod.build_pdf(design, prop, cost, before, after)
    except Exception:
        app.logger.exception("pdf failed")
        return jsonify({"error": "pdf generation failed"}), 500
    addr = (design["address"] or "design").split(",")[0]
    fname = "Land-View - " + "".join(c for c in addr if c.isalnum() or c in " -") + ".pdf"
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


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
