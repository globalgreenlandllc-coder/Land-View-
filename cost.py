"""
cost.py -- Rough budget estimate from the chosen elements + sizes.

Deliberately a *rough* planning number (the spec calls it optional/approximate):
base cost per element + per-sq-ft (areas) or per-ft (linear runs), with a few
premium-material multipliers, returned as a low–high range. Not a quote.
"""
from __future__ import annotations

from elements import get_element

# Small multipliers so premium selections move the number believably.
_PREMIUM = {
    "ipe hardwood": 1.5, "natural stone": 1.35, "tile": 1.3, "granite": 1.2,
    "infinity": 1.6, "freeform": 1.15, "louvered": 1.4, "artificial turf": 2.2,
    "brick": 1.2, "pebble": 1.15, "fireplace": 1.8,
}


def _premium_factor(options: dict) -> float:
    f = 1.0
    for v in (options or {}).values():
        f *= _PREMIUM.get(str(v), 1.0)
    return f


def _money(n) -> str:
    return "${:,.0f}".format(n)


def estimate(elements, sizes=None) -> dict:
    line_items = []
    subtotal = 0.0
    for e in elements or []:
        el = get_element(e.get("type") or e.get("key"))
        if not el:
            continue
        opts = e.get("options") or {}
        size = e.get("size")
        if not isinstance(size, (int, float)) or size <= 0:
            size = el.get("default_size", 1)
        factor = _premium_factor(opts)

        if el["kind"] == "area":
            amt = (el.get("base", 0) + el.get("per_sqft", 0) * size) * factor
            unit = f"{int(size):,} sq ft"
        elif el["kind"] == "linear":
            amt = (el.get("base", 0) + el.get("per_ft", 0) * size) * factor
            unit = f"{int(size)} ft"
        else:  # point
            qty = int(size) if size else 1
            amt = el.get("base", 0) * max(1, qty) * factor
            unit = f"×{qty}" if qty > 1 else ""

        detail = ", ".join(str(v) for v in opts.values() if v and v != "none")
        line_items.append({
            "key": el["key"], "label": el["name"],
            "detail": detail, "unit": unit, "amount": round(amt),
        })
        subtotal += amt

    subtotal = round(subtotal)
    return {
        "line_items": line_items,
        "subtotal": subtotal,
        "low": round(subtotal * 0.85),
        "high": round(subtotal * 1.20),
        "formatted": {"low": _money(subtotal * 0.85), "high": _money(subtotal * 1.20)},
        "note": "Rough planning estimate based on selected elements and typical "
                "regional costs — not a quote. Final pricing varies by site, "
                "materials, and contractor.",
    }
