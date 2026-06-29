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
import os
import socket
import urllib.error
import urllib.parse

import re

from flask import Flask, jsonify, request, Response, g
from flask_cors import CORS

from netfetch import is_allowed_image_url, safe_image_fetch, MAX_IMG_BYTES, _opener as _no_redirect_opener

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

import auth
import connections as conns
import cost as cost_mod
import geo
import parcel as parcel_mod
import pdf as pdf_mod
import render
import store as designs
from elements import ELEMENTS
from styles import STYLES

# In production the Flask app also serves the built SPA (web/dist) from the same
# origin, so the whole product is one deployable service on one port.
_WEB_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "dist")
app = Flask(__name__, static_folder=_WEB_DIST, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # cap request bodies at 4 MB
# CORS only matters for the split dev setup (Vite :5174 -> Flask :8000); in prod
# the SPA is same-origin. Extra origins can be allowed via $CORS_ORIGINS (csv).
_cors_origins = [
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5173", "http://127.0.0.1:5173",
] + [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
CORS(app, resources={r"/api/*": {"origins": _cors_origins}})

# SSRF-safe image fetching lives in netfetch.py and is shared with render.py.


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "render": render.render_status()})


# ---------------------------------------------------------------------------
# Serve the built SPA (production). API 404s stay JSON; other paths -> index.html.
# ---------------------------------------------------------------------------

@app.get("/")
def _spa_root():
    if os.path.exists(os.path.join(_WEB_DIST, "index.html")):
        return app.send_static_file("index.html")
    return jsonify({"ok": True, "note": "API up; SPA not built (run web build)."})


@app.errorhandler(404)
def _spa_fallback(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found"}), 404
    if os.path.exists(os.path.join(_WEB_DIST, "index.html")):
        return app.send_static_file("index.html")
    return jsonify({"error": "not found"}), 404


# ---------------------------------------------------------------------------
# Auth: register / login / refresh / me
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/auth/register")
def auth_register():
    body = request.get_json(force=True, silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    if not _EMAIL_RE.match(email):
        return jsonify({"error": "a valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    if designs.get_user_by_email(email) is not None:
        return jsonify({"error": "an account with that email already exists"}), 409
    # The very first account to register becomes the admin.
    role = "admin" if designs.count_users() == 0 else "user"
    user = designs.create_user(email, auth.hash_password(password), role)
    designs.add_audit(user["id"], user["email"], "register", detail=f"role={role}")
    tokens = auth.issue_tokens(user["id"], user["role"])
    return jsonify({"user": user, **tokens}), 201


@app.post("/api/auth/login")
def auth_login():
    body = request.get_json(force=True, silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    row = designs.get_user_by_email(email)
    if row is None or not auth.verify_password(password, row["password_hash"]):
        return jsonify({"error": "invalid email or password"}), 401
    if row["status"] != "active":
        return jsonify({"error": "this account is suspended"}), 403
    tokens = auth.issue_tokens(row["id"], row["role"])
    user = {"id": row["id"], "email": row["email"], "role": row["role"]}
    designs.add_audit(row["id"], row["email"], "login")
    return jsonify({"user": user, **tokens})


@app.post("/api/auth/refresh")
def auth_refresh():
    body = request.get_json(force=True, silent=True) or {}
    payload = auth.verify_token(str(body.get("refresh_token", "")), kind="refresh")
    if not payload:
        return jsonify({"error": "invalid or expired refresh token"}), 401
    row = designs.get_user_by_id(payload["sub"])
    if row is None or row["status"] != "active":
        return jsonify({"error": "account unavailable"}), 401
    return jsonify(auth.issue_tokens(row["id"], row["role"]))


@app.get("/api/auth/me")
@auth.require_auth
def auth_me():
    return jsonify({"user": g.user})


# ---------------------------------------------------------------------------
# Admin (role-gated): users, API connections, analytics, audit
# ---------------------------------------------------------------------------

@app.get("/api/admin/users")
@auth.require_admin
def admin_users():
    return jsonify({"users": designs.list_users()})


@app.patch("/api/admin/users/<uid>")
@auth.require_admin
def admin_user_update(uid):
    body = request.get_json(force=True, silent=True) or {}
    if uid == g.user["id"]:
        return jsonify({"error": "you can't change your own account here"}), 400
    target = designs.get_user_by_id(uid)
    if target is None:
        return jsonify({"error": "user not found"}), 404
    if "status" in body:
        status = body["status"]
        if status not in ("active", "suspended"):
            return jsonify({"error": "status must be 'active' or 'suspended'"}), 400
        designs.set_user_status(uid, status)
        designs.add_audit(g.user["id"], g.user["email"], "user.status",
                          target=target["email"], detail=status)
    if "role" in body:
        role = body["role"]
        if role not in ("user", "admin"):
            return jsonify({"error": "role must be 'user' or 'admin'"}), 400
        designs.set_user_role(uid, role)
        designs.add_audit(g.user["id"], g.user["email"], "user.role",
                          target=target["email"], detail=role)
    return jsonify({"user": designs._user_public(designs.get_user_by_id(uid))})


@app.delete("/api/admin/users/<uid>")
@auth.require_admin
def admin_user_delete(uid):
    if uid == g.user["id"]:
        return jsonify({"error": "you can't delete your own account"}), 400
    target = designs.get_user_by_id(uid)
    if target is None:
        return jsonify({"error": "user not found"}), 404
    designs.delete_user(uid)
    designs.add_audit(g.user["id"], g.user["email"], "user.delete", target=target["email"])
    return jsonify({"ok": True})


@app.get("/api/admin/connections")
@auth.require_admin
def admin_connections():
    return jsonify({"connections": conns.list_public()})


@app.put("/api/admin/connections/<service>")
@auth.require_admin
def admin_connection_set(service):
    body = request.get_json(force=True, silent=True) or {}
    provider = str(body.get("provider", "")).strip()
    endpoint = str(body.get("endpoint", "")).strip()
    secret = body.get("secret")
    secret = str(secret) if secret else None  # empty -> keep existing
    try:
        conns.set_connection(service, provider, endpoint, secret,
                             g.user["id"], g.user["email"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    designs.add_audit(g.user["id"], g.user["email"], "connection.set",
                      target=service, detail=f"provider={provider}")
    return jsonify({"connections": conns.list_public()})


@app.delete("/api/admin/connections/<service>")
@auth.require_admin
def admin_connection_delete(service):
    conns.delete_connection(service)
    designs.add_audit(g.user["id"], g.user["email"], "connection.delete", target=service)
    return jsonify({"connections": conns.list_public()})


@app.get("/api/admin/analytics")
@auth.require_admin
def admin_analytics():
    return jsonify(designs.analytics())


@app.get("/api/admin/audit")
@auth.require_admin
def admin_audit():
    return jsonify({"audit": designs.list_audit(200)})


@app.get("/api/styles")
def styles():
    return jsonify({"styles": [
        {k: s[k] for k in ("key", "name", "blurb", "palette")} for s in STYLES
    ]})


@app.get("/api/property")
@auth.require_auth
def property_endpoint():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "address (q) required"}), 400
    try:
        result = geo.property_intake(q)
        designs.add_audit(g.user["id"], g.user["email"], "search", target=q)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"property lookup failed: {e}"}), 502


@app.get("/api/parcel")
@auth.require_auth
def parcel_endpoint():
    q = (request.args.get("q") or "").strip()
    kind = (request.args.get("kind") or "auto").strip()
    if not q:
        return jsonify({"error": "search query (q) required"}), 400
    try:
        rec = parcel_mod.lookup(q, kind)
        designs.add_audit(g.user["id"], g.user["email"], "search",
                          target=q, detail=f"kind={rec.get('kind')}")
        return jsonify(rec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        app.logger.exception("parcel lookup failed")
        return jsonify({"error": f"parcel lookup failed: {e}"}), 502


@app.get("/api/map-config")
@auth.require_auth
def map_config_endpoint():
    """Client map config. The Mapbox token is a public (pk.) client token by design."""
    cfg = conns.get_map_config()
    return jsonify({"provider": cfg["provider"],
                    "token": cfg["token"] if cfg["provider"] == "mapbox" else "",
                    "style": cfg["style"]})


@app.post("/api/render")
@auth.require_auth
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
            view=str(body.get("view", render.DEFAULT_VIEW)),
        )
        result["cost"] = cost_mod.estimate(elements or [], prop.get("sizes"))
        designs.add_audit(g.user["id"], g.user["email"], "render",
                          target=str(body.get("style", "modern")),
                          detail=("live" if not result.get("demo") else "demo"))
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
@auth.require_auth
def designs_index():
    return jsonify({"designs": designs.list_designs(g.user["id"])})


@app.post("/api/designs")
@auth.require_auth
def designs_save():
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(designs.save_design(body, g.user["id"]))
    except PermissionError:
        return jsonify({"error": "forbidden"}), 403


@app.get("/api/designs/<did>")
@auth.require_auth
def designs_get(did):
    d = designs.get_design(did, g.user["id"])
    return (jsonify(d), 200) if d else (jsonify({"error": "not found"}), 404)


@app.delete("/api/designs/<did>")
@auth.require_auth
def designs_delete(did):
    return jsonify({"ok": designs.delete_design(did, g.user["id"])})


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
            return _robust_image_fetch(u)[0]
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


def _robust_image_fetch(u: str):
    """
    Fetch an allow-listed image, retrying at smaller sizes for Esri's export
    endpoint. Esri returns HTTP 500 ("Error: bytes") when the requested pixel
    size over-zooms beyond the available native imagery resolution (common in
    lower-res rural / high-latitude areas), so we step the size down until it
    succeeds. Non-Esri URLs are fetched once as before.
    """
    try:
        return safe_image_fetch(u)
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, OSError) as first:
        if "size=" not in u:
            raise first
        for size in (512, 400, 300, 256):
            shrunk = re.sub(r"size=\d+(?:%2C|,)\d+",
                            f"size={size}%2C{size}", u)
            if shrunk == u:
                continue
            try:
                return safe_image_fetch(shrunk)
            except Exception:
                continue
        raise first


@app.get("/api/img")
def img_proxy():
    """Allow-listed same-origin image proxy for taint-free export."""
    u = request.args.get("u", "")
    if not is_allowed_image_url(u):
        return jsonify({"error": "host not allowed"}), 400
    try:
        data, ctype = _robust_image_fetch(u)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, OSError):
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
