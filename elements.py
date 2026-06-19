"""
elements.py -- Catalog of supported backyard elements.

Each element has:
  * configurable ``options`` (the per-element detail from the spec — pool shape,
    deck material, fence type, etc.) that feed into the render prompt, and
  * cost data (``base``, plus ``per_sqft`` for areas or ``per_ft`` for linear
    runs, and a ``default_size``) used by the rough cost estimator.

``kind``: "area" (sized in sq ft), "linear" (sized in ft), or "point" (a count).
"""

ELEMENTS = [
    {
        "key": "pool", "name": "Pool", "category": "Water", "kind": "area",
        "options": [
            {"key": "shape", "label": "Shape", "choices": ["rectangular", "kidney", "freeform", "lap", "infinity"]},
            {"key": "finish", "label": "Finish", "choices": ["plaster", "pebble", "tile"]},
            {"key": "water_color", "label": "Water color", "choices": ["blue", "aqua", "dark/lagoon"]},
            {"key": "coping", "label": "Coping", "choices": ["travertine", "concrete", "natural stone", "brick"]},
            {"key": "extras", "label": "Extras", "choices": ["none", "attached spa", "waterfall", "tanning ledge"]},
        ],
        "base": 45000, "per_sqft": 120, "default_size": 450,
    },
    {
        "key": "hot_tub", "name": "Hot tub / Spa", "category": "Water", "kind": "point",
        "options": [
            {"key": "type", "label": "Type", "choices": ["built-in", "portable"]},
            {"key": "seats", "label": "Seats", "choices": ["4", "6", "8"]},
        ],
        "base": 9000, "default_size": 1,
    },
    {
        "key": "deck", "name": "Deck", "category": "Hardscape", "kind": "area",
        "options": [
            {"key": "material", "label": "Material", "choices": ["cedar", "redwood", "composite", "ipe hardwood"]},
            {"key": "color", "label": "Color/stain", "choices": ["natural", "gray", "brown", "espresso"]},
            {"key": "levels", "label": "Levels", "choices": ["single", "multi-level"]},
        ],
        "base": 3000, "per_sqft": 40, "default_size": 350,
    },
    {
        "key": "patio", "name": "Patio", "category": "Hardscape", "kind": "area",
        "options": [
            {"key": "material", "label": "Material", "choices": ["pavers", "natural stone", "stamped concrete", "brick", "gravel"]},
            {"key": "pattern", "label": "Pattern", "choices": ["running bond", "herringbone", "ashlar", "random"]},
            {"key": "color", "label": "Color", "choices": ["tan", "gray", "charcoal", "buff"]},
        ],
        "base": 1500, "per_sqft": 22, "default_size": 400,
    },
    {
        "key": "pergola", "name": "Pergola", "category": "Structure", "kind": "point",
        "options": [
            {"key": "material", "label": "Material", "choices": ["cedar", "aluminum", "vinyl"]},
            {"key": "roof", "label": "Roof", "choices": ["open slats", "louvered", "solid"]},
            {"key": "size", "label": "Size", "choices": ["10x10", "12x16", "16x20"]},
        ],
        "base": 7000, "default_size": 1,
    },
    {
        "key": "gazebo", "name": "Gazebo", "category": "Structure", "kind": "point",
        "options": [
            {"key": "material", "label": "Material", "choices": ["cedar", "composite", "metal"]},
            {"key": "roof", "label": "Roof", "choices": ["shingle", "metal", "thatch"]},
            {"key": "size", "label": "Size", "choices": ["10ft", "12ft", "14ft"]},
        ],
        "base": 11000, "default_size": 1,
    },
    {
        "key": "fire", "name": "Fire feature", "category": "Structure", "kind": "point",
        "options": [
            {"key": "type", "label": "Type", "choices": ["fire pit", "fireplace"]},
            {"key": "material", "label": "Material", "choices": ["natural stone", "concrete", "steel"]},
            {"key": "seating", "label": "Seating", "choices": ["none", "built-in bench", "chairs"]},
        ],
        "base": 4500, "default_size": 1,
    },
    {
        "key": "sauna", "name": "Sauna", "category": "Structure", "kind": "point",
        "options": [
            {"key": "material", "label": "Material", "choices": ["cedar", "thermo-wood"]},
            {"key": "size", "label": "Size", "choices": ["2-person", "4-person", "6-person"]},
        ],
        "base": 13000, "default_size": 1,
    },
    {
        "key": "kitchen", "name": "Outdoor kitchen", "category": "Structure", "kind": "point",
        "options": [
            {"key": "counter", "label": "Counter", "choices": ["granite", "concrete", "tile"]},
            {"key": "layout", "label": "Layout", "choices": ["straight", "L-shaped", "island"]},
            {"key": "bar_seating", "label": "Bar seating", "choices": ["yes", "no"]},
            {"key": "cover", "label": "Cover", "choices": ["none", "pergola"]},
        ],
        "base": 16000, "default_size": 1,
    },
    {
        "key": "fence", "name": "Fence", "category": "Boundary", "kind": "linear",
        "options": [
            {"key": "type", "label": "Type", "choices": ["privacy", "picket", "horizontal slat", "wrought iron"]},
            {"key": "material", "label": "Material", "choices": ["cedar", "vinyl", "stone", "brick"]},
            {"key": "height", "label": "Height", "choices": ["4 ft", "6 ft", "8 ft"]},
            {"key": "stain", "label": "Color/stain", "choices": ["natural", "gray", "black", "white"]},
        ],
        "base": 0, "per_ft": 40, "default_size": 120,
    },
    {
        "key": "wall", "name": "Retaining wall", "category": "Boundary", "kind": "linear",
        "options": [
            {"key": "material", "label": "Material", "choices": ["natural stone", "concrete block", "timber"]},
            {"key": "height", "label": "Height", "choices": ["2 ft", "3 ft", "4 ft"]},
        ],
        "base": 0, "per_ft": 65, "default_size": 40,
    },
    {
        "key": "beds", "name": "Garden beds", "category": "Planting", "kind": "area",
        "options": [
            {"key": "planting", "label": "Planting", "choices": ["perennials", "shrubs", "mixed", "vegetables"]},
            {"key": "drought_tolerant", "label": "Low-water", "choices": ["no", "yes"]},
        ],
        "base": 500, "per_sqft": 14, "default_size": 200,
    },
    {
        "key": "lawn", "name": "Lawn / ground cover", "category": "Planting", "kind": "area",
        "options": [
            {"key": "type", "label": "Type", "choices": ["sod", "ground cover", "artificial turf"]},
        ],
        "base": 300, "per_sqft": 4, "default_size": 800,
    },
    {
        "key": "trees", "name": "Trees & plants", "category": "Planting", "kind": "point",
        "options": [
            {"key": "type", "label": "Type", "choices": ["shade trees", "palms", "evergreens", "ornamental"]},
            {"key": "density", "label": "Density", "choices": ["sparse", "medium", "dense"]},
        ],
        "base": 2000, "default_size": 1,
    },
    {
        "key": "pathway", "name": "Pathway", "category": "Hardscape", "kind": "linear",
        "options": [
            {"key": "material", "label": "Material", "choices": ["flagstone", "pavers", "gravel", "stepping stone"]},
            {"key": "width", "label": "Width", "choices": ["2 ft", "3 ft", "4 ft"]},
            {"key": "layout", "label": "Layout", "choices": ["straight", "curved", "stepping"]},
        ],
        "base": 0, "per_ft": 28, "default_size": 40,
    },
    {
        "key": "lighting", "name": "Outdoor lighting", "category": "Lighting", "kind": "point",
        "options": [
            {"key": "type", "label": "Type", "choices": ["pathway", "uplighting", "string lights", "mixed"]},
        ],
        "base": 2800, "default_size": 1,
    },
    {
        "key": "seating", "name": "Seating area", "category": "Structure", "kind": "point",
        "options": [
            {"key": "type", "label": "Type", "choices": ["lounge", "dining", "fire-side"]},
            {"key": "cover", "label": "Cover", "choices": ["none", "umbrella", "pergola"]},
        ],
        "base": 3500, "default_size": 1,
    },
]

_BY_KEY = {e["key"]: e for e in ELEMENTS}


def get_element(key: str):
    return _BY_KEY.get(key)


def default_options(key: str) -> dict:
    el = _BY_KEY.get(key)
    return {o["key"]: o["choices"][0] for o in el["options"]} if el else {}
