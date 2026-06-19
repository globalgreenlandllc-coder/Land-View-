"""
styles.py -- Named design style presets.

Each preset drives the AI's material/plant/color/mood choices automatically so a
client can pick a vibe instead of describing everything. ``prompt_fragment`` is
the text injected into the image-generation prompt; the rest is for the UI.
"""

STYLES = [
    {
        "key": "modern",
        "name": "Modern / Contemporary",
        "blurb": "Clean lines, concrete and steel, rectangular pool, minimal planting.",
        "palette": ["#e7e5e4", "#3f3f46", "#0ea5e9", "#1c1917"],
        "materials": "poured concrete, steel, large-format porcelain pavers, glass",
        "plants": "architectural grasses, clipped boxwood, a few sculptural trees",
        "prompt_fragment": ("modern contemporary landscape design, clean geometric "
                            "lines, rectangular swimming pool, poured-concrete and "
                            "large-format porcelain patio, steel and glass accents, "
                            "minimal restrained planting with ornamental grasses, "
                            "neutral monochrome palette"),
    },
    {
        "key": "mediterranean",
        "name": "Mediterranean / Tuscan",
        "blurb": "Terracotta, stucco, stone, olive and cypress trees, warm earth tones.",
        "palette": ["#d6a76b", "#a8553a", "#8a9a5b", "#efe6d5"],
        "materials": "terracotta tile, stucco walls, travertine, natural stone",
        "plants": "olive trees, Italian cypress, lavender, rosemary, citrus",
        "prompt_fragment": ("Mediterranean Tuscan landscape, terracotta tile and "
                            "travertine patio, stucco garden walls, olive trees and "
                            "tall Italian cypress, lavender and rosemary beds, warm "
                            "earth-tone palette, wrought-iron accents"),
    },
    {
        "key": "tropical",
        "name": "Tropical / Resort",
        "blurb": "Lush palms, lagoon-style pool, natural stone, bamboo, water features.",
        "palette": ["#0f766e", "#16a34a", "#f59e0b", "#0c4a6e"],
        "materials": "natural stone, bamboo, hardwood decking, pebble pool finish",
        "plants": "palms, banana, bird of paradise, bamboo, ferns, hibiscus",
        "prompt_fragment": ("lush tropical resort backyard, freeform lagoon-style "
                            "pool with natural stone coping and waterfall, dense "
                            "palms, banana plants, bird of paradise and bamboo, "
                            "hardwood deck, cabana, vibrant resort atmosphere"),
    },
    {
        "key": "rustic",
        "name": "Rustic / Farmhouse",
        "blurb": "Natural wood, gravel paths, raised garden beds, fire pit, wildflowers.",
        "palette": ["#6b4f2a", "#9ca3af", "#84cc16", "#b91c1c"],
        "materials": "weathered cedar, gravel, fieldstone, galvanized metal",
        "plants": "raised vegetable beds, wildflowers, fruit trees, ornamental grasses",
        "prompt_fragment": ("rustic farmhouse backyard, natural weathered cedar "
                            "structures, gravel pathways, raised wooden garden beds, "
                            "stone fire pit with Adirondack seating, wildflower "
                            "borders, relaxed country atmosphere"),
    },
    {
        "key": "japanese",
        "name": "Japanese / Zen",
        "blurb": "Gravel, stepping stones, maples, water basin, restrained planting.",
        "palette": ["#9aa39b", "#3f4a3c", "#b45309", "#1f2937"],
        "materials": "raked gravel, granite stepping stones, bamboo, dark timber",
        "plants": "Japanese maples, moss, mounded shrubs, black pine, ferns",
        "prompt_fragment": ("Japanese zen garden, raked gravel, granite stepping "
                            "stones, Japanese maples, moss, a stone water basin "
                            "(tsukubai), bamboo screen, restrained meditative "
                            "planting, tranquil balanced composition"),
    },
    {
        "key": "desert",
        "name": "Desert / Xeriscape",
        "blurb": "Drought-tolerant plants, succulents, gravel, boulders, low water use.",
        "palette": ["#c2853b", "#7c2d12", "#65a30d", "#e7d8c0"],
        "materials": "decomposed granite, flagstone, corten steel, boulders",
        "plants": "agave, cactus, succulents, ocotillo, desert spoon, palo verde",
        "prompt_fragment": ("desert xeriscape landscape, decomposed-granite ground, "
                            "sculptural agave, cactus and succulents, large boulders, "
                            "flagstone patio, corten-steel planters, palo verde "
                            "trees, low-water arid palette under bright sun"),
    },
    {
        "key": "classic",
        "name": "Classic / Traditional",
        "blurb": "Symmetrical layout, manicured hedges, brick, formal lawns.",
        "palette": ["#7f1d1d", "#166534", "#e5e7eb", "#44403c"],
        "materials": "brick, bluestone, painted wood, wrought iron",
        "plants": "clipped boxwood hedges, roses, formal lawn, topiary",
        "prompt_fragment": ("classic traditional formal garden, symmetrical layout, "
                            "manicured boxwood hedges and topiary, brick and bluestone "
                            "paths, formal manicured lawn, rose beds, elegant "
                            "wrought-iron furniture, timeless refined look"),
    },
    {
        "key": "coastal",
        "name": "Coastal",
        "blurb": "Light woods, beach grasses, weathered finishes, breezy open layout.",
        "palette": ["#cbd5e1", "#0ea5e9", "#eab308", "#f8fafc"],
        "materials": "weathered gray wood, white-washed surfaces, pale gravel, rope",
        "plants": "beach grasses, hydrangea, lavender, dune-style plantings",
        "prompt_fragment": ("coastal backyard, weathered gray wood deck, white-washed "
                            "surfaces, ornamental beach grasses and hydrangea, pale "
                            "gravel, breezy open layout, soft blue-and-sand palette, "
                            "bright airy seaside mood"),
    },
]

_BY_KEY = {s["key"]: s for s in STYLES}


def get_style(key: str) -> dict:
    return _BY_KEY.get(key, STYLES[0])
