"""
parcel.py -- Parcel / property data with a pluggable provider abstraction.

A "parcel record" is the canonical shape the rest of the app consumes:

    {
      "query", "kind",                       # what was searched
      "address", "lat", "lng",
      "apn", "owner", "zoning",
      "lot_size_sqft", "assessed_value",
      "dimensions": {"frontage_ft", "depth_ft"},
      "boundary": [[lng,lat], ...],          # closed ring (GeoJSON order)
      "satellite_url", "sizes": {...},       # from geo.py (scale/house/backyard)
      "provider", "demo", "note"
    }

Providers (selected from Admin → API Connections, service "parcel"):
  * demo     -> no key; derives a real-shaped boundary from the geocoded lot and
                synthesizes plausible owner/APN/zoning/assessed-value. Marked demo.
  * regrid   -> Regrid Parcels API (needs token); real boundaries + attributes.
  * attom    -> ATTOM property API (needs key).
The real providers degrade gracefully to demo if not configured or on error, so
the UI always works; swapping providers needs no code change.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.parse
import urllib.request

import geo

_UA = {"User-Agent": "Land-View/1.0 (landscape design tool)"}
_ZONING = ["R-1 Single-Family", "R-2 Two-Family", "R-3 Multi-Family",
           "RA Residential-Agricultural", "RR Rural Residential", "PUD Planned Unit"]
_OWNER_SUFFIX = ["FAMILY TRUST", "HOLDINGS LLC", "PROPERTIES LLC", "REVOCABLE TRUST", ""]
_OWNER_STEM = ["MERIDIAN", "OAKHURST", "CEDAR RIDGE", "STONEGATE", "LAKEVIEW",
               "BIRCHWOOD", "SUMMIT", "WILLOW CREEK", "HIGHLAND", "PINEHURST"]


# ---------------------------------------------------------------------------
# Query parsing
# ---------------------------------------------------------------------------

def parse_query(q: str, kind: str = "auto"):
    """Return (kind, payload). kind in {address, apn, coords}."""
    q = (q or "").strip()
    if not q:
        raise ValueError("a search query is required")
    if kind == "auto":
        coords = _try_coords(q)
        if coords:
            return "coords", coords
        if _looks_like_apn(q):
            return "apn", q
        return "address", q
    if kind == "coords":
        coords = _try_coords(q)
        if not coords:
            raise ValueError("expected coordinates like '34.05, -118.24'")
        return "coords", coords
    return kind, q


def _try_coords(q: str):
    parts = [p.strip() for p in q.replace(";", ",").split(",")]
    if len(parts) != 2:
        return None
    try:
        lat, lng = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return (lat, lng)
    return None


def _looks_like_apn(q: str):
    digits = sum(c.isdigit() for c in q)
    # APNs are mostly digits with dashes/dots and no spaces; addresses have words.
    return digits >= 6 and " " not in q and any(c in q for c in "-.")


# ---------------------------------------------------------------------------
# Deterministic synthesis helpers (demo provider)
# ---------------------------------------------------------------------------

def _seed(lat: float, lng: float) -> int:
    h = hashlib.sha256(f"{round(lat,5)},{round(lng,5)}".encode()).hexdigest()
    return int(h[:12], 16)


def _rect_boundary(lat: float, lng: float, lot_sqft: float):
    """Build a closed rectangular ring (GeoJSON [lng,lat]) centered on the point."""
    area_m2 = lot_sqft / geo.SQM_TO_SQFT
    seed = _seed(lat, lng)
    ratio = 0.7 + (seed % 70) / 100.0          # frontage/depth between 0.7 and 1.4
    depth_m = math.sqrt(area_m2 / ratio)
    frontage_m = area_m2 / depth_m
    dlat = (depth_m / 2) / geo.M_PER_DEG_LAT
    dlng = (frontage_m / 2) / geo.m_per_deg_lng(lat)
    ring = [
        [lng - dlng, lat - dlat], [lng + dlng, lat - dlat],
        [lng + dlng, lat + dlat], [lng - dlng, lat + dlat],
        [lng - dlng, lat - dlat],
    ]
    return ring, round(frontage_m * 3.28084), round(depth_m * 3.28084)


def _synth_attrs(lat: float, lng: float, lot_sqft: float):
    seed = _seed(lat, lng)
    apn = f"{seed % 1000:03d}-{(seed >> 6) % 1000:03d}-{(seed >> 12) % 1000:03d}"
    stem = _OWNER_STEM[seed % len(_OWNER_STEM)]
    suffix = _OWNER_SUFFIX[(seed >> 4) % len(_OWNER_SUFFIX)]
    owner = (stem + " " + suffix).strip()
    zoning = _ZONING[(seed >> 8) % len(_ZONING)]
    # Assessed value: rough $/sqft of land + a structure premium, deterministic.
    per_sqft = 8 + (seed % 22)               # $8–$30 / sqft land
    assessed = int(round((lot_sqft * per_sqft + 120_000 + (seed % 80) * 1000) / 1000.0) * 1000)
    return apn, owner, zoning, assessed


# ---------------------------------------------------------------------------
# Site intelligence: structure zones, setbacks, designable area
# ---------------------------------------------------------------------------

def _ring_area_sqft(ring) -> float:
    if not ring or len(ring) < 3:
        return 0.0
    return geo._polygon_area_sqft([(lat, lng) for lng, lat in ring])  # (lat,lng)


def _setback_ring(ring, setback_ft: float = 15.0):
    """Inset the boundary toward its centroid by ~setback_ft (a no-build guide)."""
    if not ring or len(ring) < 4:
        return None
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    mlat, mlng = geo.M_PER_DEG_LAT, geo.m_per_deg_lng(cy)
    setback_m = setback_ft / 3.28084
    out = []
    for lng, lat in pts:
        dx, dy = (lng - cx) * mlng, (lat - cy) * mlat
        d = math.hypot(dx, dy)
        f = (d - setback_m) / d if d > setback_m else 0.0
        out.append([cx + (lng - cx) * f, cy + (lat - cy) * f])
    out.append(out[0])  # close the ring
    return out


def _site_intelligence(rec: dict) -> dict:
    """Attach structures (no-design zones), setback guide, and designable area."""
    ring = rec.get("boundary")
    structures = []
    fp = geo.house_footprint(rec["lat"], rec["lng"])
    if fp and fp.get("ring"):
        structures.append(fp["ring"])
    setback = _setback_ring(ring) if ring else None
    designable = None
    if setback:
        designable = _ring_area_sqft(setback) - sum(_ring_area_sqft(s) for s in structures)
        designable = max(0, round(designable))
    rec["structures"] = structures
    rec["setback"] = setback
    rec["designable_sqft"] = designable
    return rec


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def lookup(query: str, kind: str = "auto") -> dict:
    kind, payload = parse_query(query, kind)
    import connections
    cfg = connections.get_parcel_config()
    provider = cfg.get("provider") or "demo"

    if provider in ("regrid", "attom") and cfg.get("api_key"):
        try:
            return _real_provider(provider, cfg, kind, payload, query)
        except Exception as exc:  # graceful: never break the UX on a provider error
            import sys
            print(f"[parcel] provider '{provider}' failed: {exc}", file=sys.stderr)
            rec = _demo_lookup(kind, payload, query)
            rec["note"] = (f"{provider} lookup failed — showing demo parcel data. "
                           "Check the provider key in Admin → API Connections.")
            return rec
    return _demo_lookup(kind, payload, query)


def _demo_lookup(kind: str, payload, query: str) -> dict:
    # Resolve to a point + the existing geo intake (satellite, scale, sizes).
    if kind == "coords":
        lat, lng = payload
        intake = {
            "address": f"{lat:.5f}, {lng:.5f}",
            "lat": lat, "lng": lng,
            "satellite_url": geo.esri_satellite_url(lat, lng, span_m=120),
            "sizes": {"lot_sqft": None, "house_sqft": geo.house_footprint_sqft(lat, lng),
                      "backyard_sqft": None, "view_width_ft": round(120 * 3.28084)},
            "scale_note": "Coordinate search (demo parcel data).",
        }
    else:
        # address or apn — geocode the text (an APN string still geocodes poorly,
        # so for apn we note it's demo-resolved).
        intake = geo.property_intake(query if kind == "address" else query)
        lat, lng = intake["lat"], intake["lng"]

    lot_sqft = intake["sizes"].get("lot_sqft") or _fallback_lot(lat, lng)
    boundary, frontage_ft, depth_ft = _rect_boundary(lat, lng, lot_sqft)
    apn, owner, zoning, assessed = _synth_attrs(lat, lng, lot_sqft)
    # If the search was by APN, surface the searched APN rather than a synthetic one.
    if kind == "apn":
        apn = query
    intake["sizes"]["lot_sqft"] = intake["sizes"].get("lot_sqft") or lot_sqft

    return _site_intelligence({
        "query": query, "kind": kind,
        "address": intake["address"], "lat": lat, "lng": lng,
        "apn": apn, "owner": owner, "zoning": zoning,
        "lot_size_sqft": lot_sqft, "assessed_value": assessed,
        "dimensions": {"frontage_ft": frontage_ft, "depth_ft": depth_ft},
        "boundary": boundary,
        "satellite_url": intake["satellite_url"],
        "sizes": intake["sizes"],
        "provider": "demo", "demo": True,
        "note": "Demo parcel data — boundary and attributes are estimated, not a "
                "survey. Connect Regrid or ATTOM in Admin → API Connections for "
                "authoritative parcels.",
    })


def _fallback_lot(lat: float, lng: float) -> int:
    # Plausible suburban lot if geo couldn't estimate one: 5,000–12,000 sqft.
    return 5000 + (_seed(lat, lng) % 7000)


# ---------------------------------------------------------------------------
# Real providers (activated when a key is configured)
# ---------------------------------------------------------------------------

def _real_provider(provider: str, cfg: dict, kind: str, payload, query: str) -> dict:
    if provider == "regrid":
        return _regrid(cfg, kind, payload, query)
    if provider == "attom":
        return _attom(cfg, kind, payload, query)
    raise ValueError(f"unknown parcel provider {provider}")


def _regrid(cfg: dict, kind: str, payload, query: str) -> dict:
    """Regrid Parcels API — returns real boundary geometry + parcel fields."""
    token = cfg["api_key"]
    base = cfg.get("endpoint") or "https://app.regrid.com/api/v2"
    if kind == "coords":
        lat, lng = payload
        url = f"{base}/parcels/point?" + urllib.parse.urlencode(
            {"lat": lat, "lon": lng, "token": token})
    else:
        url = f"{base}/parcels/address?" + urllib.parse.urlencode(
            {"query": query, "token": token})
    req = urllib.request.Request(url, headers={**_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    feat = (data.get("parcels", {}).get("features") or data.get("features") or [None])[0]
    if not feat:
        raise ValueError("no parcel returned")
    props = feat.get("properties", {}).get("fields", feat.get("properties", {}))
    ring = _first_ring(feat.get("geometry"))
    lat, lng = _ring_centroid(ring)
    lot_sqft = _num(props.get("ll_gissqft")) or _num(props.get("sqft")) or 0
    return _assemble_real("regrid", query, kind, lat, lng, ring, {
        "apn": props.get("parcelnumb") or props.get("apn"),
        "owner": props.get("owner"),
        "zoning": props.get("zoning") or props.get("usedesc"),
        "lot_size_sqft": lot_sqft or None,
        "assessed_value": _num(props.get("parval")) or _num(props.get("landval")),
    })


def _attom(cfg: dict, kind: str, payload, query: str) -> dict:
    """ATTOM property detail — attributes + a bbox-based boundary fallback."""
    key = cfg["api_key"]
    base = cfg.get("endpoint") or "https://api.gateway.attomdata.com/propertyapi/v1.0.0"
    url = f"{base}/property/detail?" + urllib.parse.urlencode({"address1": query})
    req = urllib.request.Request(url, headers={**_UA, "Accept": "application/json",
                                               "apikey": key})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    prop = (data.get("property") or [None])[0]
    if not prop:
        raise ValueError("no property returned")
    loc = prop.get("location", {})
    lat, lng = float(loc.get("latitude")), float(loc.get("longitude"))
    lot_sqft = _num(prop.get("lot", {}).get("lotsize2"))  # sqft
    ring, fr, dp = _rect_boundary(lat, lng, lot_sqft or _fallback_lot(lat, lng))
    rec = _assemble_real("attom", query, kind, lat, lng, ring, {
        "apn": prop.get("identifier", {}).get("apn"),
        "owner": (prop.get("owner", {}).get("owner1", {}) or {}).get("lastname"),
        "zoning": prop.get("lot", {}).get("zoningtype"),
        "lot_size_sqft": lot_sqft,
        "assessed_value": _num(prop.get("assessment", {}).get("assessed", {}).get("assdttlvalue")),
    })
    rec["dimensions"] = {"frontage_ft": fr, "depth_ft": dp}
    return rec


def _assemble_real(provider, query, kind, lat, lng, ring, attrs) -> dict:
    lot = attrs.get("lot_size_sqft") or _fallback_lot(lat, lng)
    _, fr, dp = _rect_boundary(lat, lng, lot)
    return _site_intelligence({
        "query": query, "kind": kind,
        "address": query, "lat": lat, "lng": lng,
        "apn": attrs.get("apn") or "—",
        "owner": attrs.get("owner") or "—",
        "zoning": attrs.get("zoning") or "—",
        "lot_size_sqft": attrs.get("lot_size_sqft") or lot,
        "assessed_value": attrs.get("assessed_value"),
        "dimensions": {"frontage_ft": fr, "depth_ft": dp},
        "boundary": ring,
        "satellite_url": geo.esri_satellite_url(lat, lng, span_m=120),
        "sizes": {"lot_sqft": attrs.get("lot_size_sqft") or lot,
                  "house_sqft": geo.house_footprint_sqft(lat, lng),
                  "backyard_sqft": None, "view_width_ft": round(120 * 3.28084)},
        "provider": provider, "demo": False, "note": None,
    })


def _first_ring(geom):
    if not geom:
        raise ValueError("no geometry")
    t, coords = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return coords[0]
    if t == "MultiPolygon":
        return coords[0][0]
    raise ValueError(f"unsupported geometry {t}")


def _ring_centroid(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return (sum(ys) / len(ys), sum(xs) / len(xs))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
