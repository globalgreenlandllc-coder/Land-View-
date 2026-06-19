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
    """Address -> {lat, lng, display_name, bbox:[s,n,w,e]} via Nominatim."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "addressdetails": 0})
    hits = _get_json(url)
    if not hits:
        raise ValueError("address not found")
    h = hits[0]
    s, n, w, e = (float(x) for x in h["boundingbox"])  # [south, north, west, east]
    return {
        "lat": float(h["lat"]), "lng": float(h["lon"]),
        "display_name": h.get("display_name", q),
        "osm_bbox": [s, n, w, e],
    }


# ---------------------------------------------------------------------------
# View bbox + satellite URL + scale
# ---------------------------------------------------------------------------

def view_bbox(lat: float, lng: float, span_m: float = 120.0):
    """Square-ish bbox (in degrees) ~span_m across, centred on the point."""
    dlat = (span_m / 2) / M_PER_DEG_LAT
    dlng = (span_m / 2) / m_per_deg_lng(lat)
    return {"south": lat - dlat, "north": lat + dlat,
            "west": lng - dlng, "east": lng + dlng}


def esri_satellite_url(bbox: dict, size_px: int = 700) -> str:
    """Esri World Imagery export URL for a lat/lng bbox (EPSG:4326)."""
    params = {
        "bbox": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
        "bboxSR": 4326, "imageSR": 4326,
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
    s, n, w, e = g["osm_bbox"]

    # Lot estimate from the OSM bounding box (approximate).
    lot_sqft = round(_bbox_area_sqft(s, n, w, e))
    house_sqft = house_footprint_sqft(lat, lng)

    # Backyard ~ usable open space: a fraction of lot minus house (rough heuristic).
    if lot_sqft:
        backyard_sqft = max(0, round((lot_sqft - (house_sqft or lot_sqft * 0.18)) * 0.45))
    else:
        backyard_sqft = None

    bbox = view_bbox(lat, lng, span_m=120)
    width_m = (bbox["east"] - bbox["west"]) * m_per_deg_lng(lat)

    return {
        "address": g["display_name"],
        "lat": lat, "lng": lng,
        "bbox": bbox,
        "satellite_url": esri_satellite_url(bbox),
        "sizes": {
            "lot_sqft": lot_sqft or None,
            "house_sqft": house_sqft,
            "backyard_sqft": backyard_sqft,
            "view_width_ft": round(width_m * 3.28084),
        },
        "scale_note": "Approximate, derived from map imagery — confirm on site.",
    }
