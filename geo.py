"""
geo.py -- Property intake: geocode an address, fetch satellite imagery, and
estimate real-world scale + lot / house / backyard sizes.

All free / no-key for the MVP:
  * Geocoding + a bounding box -> OpenStreetMap Nominatim
  * Satellite imagery        -> Esri "World Imagery" export (public REST service)
  * House footprint (best effort) -> OpenStreetMap Overpass

Sizes are approximate (the spec allows this). For precise lot boundaries in
production, swap in a parcel API (e.g. Regrid).
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

_UA = {"User-Agent": "Land-View/1.0 (landscape design tool)"}
M_PER_DEG_LAT = 111_320.0
SQM_TO_SQFT = 10.7639
_MERC_R = 6_378_137.0  # Web Mercator earth radius (m)

# A Nominatim bbox larger than this almost certainly isn't a single lot (city /
# region / vague query) — treat the lot size as unknown rather than report nonsense.
_MAX_LOT_SQFT = 1_000_000  # ~23 acres

ESRI_EXPORT = ("https://services.arcgisonline.com/arcgis/rest/services/"
               "World_Imagery/MapServer/export")


def _get_json(url: str, timeout=12):
    req = urllib.request.Request(url, headers={**_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def m_per_deg_lng(lat: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat))


# ---------------------------------------------------------------------------
# Geocode
# ---------------------------------------------------------------------------

def geocode(q: str) -> dict:
    """
    Address -> {lat, lng, display_name, osm_bbox:[s,n,w,e]|None}.
    Provider is chosen from Admin → API Connections (service "geocoding"):
    nominatim (free, default) | google | mapbox. Falls back to Nominatim if a
    keyed provider errors, so search always works.
    """
    import connections
    cfg = connections.get_geocode_config()
    provider = (cfg.get("provider") or "nominatim").lower()
    key = cfg.get("api_key") or ""
    try:
        if provider == "google" and key:
            return _geocode_google(q, key)
        if provider == "mapbox" and key:
            return _geocode_mapbox(q, key)
    except ValueError:
        raise  # genuine "not found" — don't mask it
    except Exception as exc:  # provider/auth/network error -> fall back
        import sys
        print(f"[geocode] provider '{provider}' failed: {exc}; using Nominatim",
              file=sys.stderr)
    return _geocode_nominatim(q)


def _geocode_nominatim(q: str) -> dict:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "addressdetails": 0})
    hits = _get_json(url)
    if not hits:
        raise ValueError("address not found")
    h = hits[0]
    bb = h.get("boundingbox")
    osm_bbox = None
    if bb and len(bb) == 4:
        try:
            osm_bbox = [float(x) for x in bb]  # [south, north, west, east]
        except (TypeError, ValueError):
            osm_bbox = None
    return {"lat": float(h["lat"]), "lng": float(h["lon"]),
            "display_name": h.get("display_name", q), "osm_bbox": osm_bbox}


def _geocode_google(q: str, key: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(
        {"address": q, "key": key})
    data = _get_json(url)
    status = data.get("status")
    if status == "ZERO_RESULTS":
        raise ValueError("address not found")
    if status != "OK" or not data.get("results"):
        raise RuntimeError(f"google geocode status {status}: {data.get('error_message', '')}")
    r = data["results"][0]
    loc = r["geometry"]["location"]
    box = r["geometry"].get("bounds") or r["geometry"].get("viewport")
    osm_bbox = None
    if box:
        ne, sw = box["northeast"], box["southwest"]
        osm_bbox = [sw["lat"], ne["lat"], sw["lng"], ne["lng"]]  # [s, n, w, e]
    return {"lat": float(loc["lat"]), "lng": float(loc["lng"]),
            "display_name": r.get("formatted_address", q), "osm_bbox": osm_bbox}


def _geocode_mapbox(q: str, token: str) -> dict:
    url = (f"https://api.mapbox.com/geocoding/v5/mapbox.places/"
           f"{urllib.parse.quote(q)}.json?" + urllib.parse.urlencode(
               {"access_token": token, "limit": 1}))
    data = _get_json(url)
    feats = data.get("features") or []
    if not feats:
        raise ValueError("address not found")
    f = feats[0]
    lng, lat = f["center"]
    osm_bbox = None
    if f.get("bbox") and len(f["bbox"]) == 4:
        w, s, e, n = f["bbox"]
        osm_bbox = [s, n, w, e]
    return {"lat": float(lat), "lng": float(lng),
            "display_name": f.get("place_name", q), "osm_bbox": osm_bbox}


# ---------------------------------------------------------------------------
# View bbox + satellite URL + scale
# ---------------------------------------------------------------------------

def _to_mercator(lat: float, lng: float):
    """WGS84 -> Web Mercator (EPSG:3857) metres."""
    x = _MERC_R * math.radians(lng)
    y = _MERC_R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def esri_satellite_url(lat: float, lng: float, span_m: float = 120.0,
                       size_px: int = 700) -> str:
    """
    Esri World Imagery export URL, requested in Web Mercator (EPSG:3857) with a
    square-in-metres bbox into a square pixel frame, so the returned imagery is
    NOT geometrically distorted (the 4326 path stretched longitude away from the
    equator). ``span_m`` is the approximate ground width shown.
    """
    # Mercator over-scales by 1/cos(lat); compensate so the ground span ~= span_m.
    merc_half = (span_m / math.cos(math.radians(lat))) / 2
    x, y = _to_mercator(lat, lng)
    params = {
        "bbox": f"{x - merc_half},{y - merc_half},{x + merc_half},{y + merc_half}",
        "bboxSR": 3857, "imageSR": 3857,
        "size": f"{size_px},{size_px}",
        "format": "jpg", "f": "image",
    }
    return ESRI_EXPORT + "?" + urllib.parse.urlencode(params)


def _bbox_area_sqft(s, n, w, e) -> float:
    lat_mid = (s + n) / 2
    height_m = (n - s) * M_PER_DEG_LAT
    width_m = (e - w) * m_per_deg_lng(lat_mid)
    return abs(width_m * height_m) * SQM_TO_SQFT


# ---------------------------------------------------------------------------
# House footprint (best effort, OSM Overpass)
# ---------------------------------------------------------------------------

def _polygon_area_sqft(coords) -> float:
    """Shoelace area for [[lat,lng],...] in square feet."""
    if len(coords) < 3:
        return 0.0
    lat0 = coords[0][0]
    mlng = m_per_deg_lng(lat0)
    pts = [((lng) * mlng, (lat) * M_PER_DEG_LAT) for lat, lng in coords]
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 * SQM_TO_SQFT


def house_footprint_sqft(lat: float, lng: float) -> float | None:
    """Nearest building footprint area near the point, if OSM has one."""
    q = (f"[out:json][timeout:10];way(around:35,{lat},{lng})[building];"
         f"out geom;")
    try:
        data = _get_json("https://overpass-api.de/api/interpreter?" +
                         urllib.parse.urlencode({"data": q}))
    except Exception:
        return None
    best = None
    for el in data.get("elements", []):
        geom = el.get("geometry")
        if not geom:
            continue
        coords = [(g["lat"], g["lon"]) for g in geom]
        area = _polygon_area_sqft(coords)
        if area > 0 and (best is None or area > best):
            best = area
    return round(best) if best else None


# ---------------------------------------------------------------------------
# Public: full property intake
# ---------------------------------------------------------------------------

def property_intake(address: str) -> dict:
    g = geocode(address)
    lat, lng = g["lat"], g["lng"]

    warnings = []

    # Lot estimate from the OSM bounding box (rough). The Nominatim bbox is only a
    # proxy for the parcel and can be off by a lot, so we clamp obviously-wrong
    # values to None rather than report nonsense (a parcel API gives true lots).
    lot_sqft = None
    if g["osm_bbox"]:
        s, n, w, e = g["osm_bbox"]
        raw = round(_bbox_area_sqft(s, n, w, e))
        if 0 < raw <= _MAX_LOT_SQFT:
            lot_sqft = raw
        else:
            warnings.append("Lot size unavailable for this result (not a single parcel).")
    else:
        warnings.append("No lot boundary found for this address.")

    house_sqft = house_footprint_sqft(lat, lng)

    # Usable backyard ~ open space behind/around the house (rough heuristic).
    backyard_sqft = None
    if lot_sqft:
        open_space = lot_sqft - (house_sqft if house_sqft else round(lot_sqft * 0.20))
        cand = round(open_space * 0.5)
        backyard_sqft = cand if cand >= 200 else None
        if backyard_sqft is None:
            warnings.append("Lot too small to estimate a backyard; confirm on site.")

    span_m = 120
    return {
        "address": g["display_name"],
        "lat": lat, "lng": lng,
        "satellite_url": esri_satellite_url(lat, lng, span_m=span_m),
        "sizes": {
            "lot_sqft": lot_sqft,
            "house_sqft": house_sqft,
            "backyard_sqft": backyard_sqft,
            "view_width_ft": round(span_m * 3.28084),  # satellite frame width, not the lot
        },
        "scale_note": "Rough estimates from map imagery — confirm on site. "
                      "Connect a parcel API for exact lot boundaries."
                      + ((" " + " ".join(warnings)) if warnings else ""),
    }
