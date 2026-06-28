"""
render.py -- The render pipeline: turn (property + style + vision + elements) into
a detailed, property-accurate photorealistic image prompt, then hand it to an
image-generation provider.

Realism is the whole point, so the prompt is engineered to:
  * CONDITION ON the real satellite image (same house, same lot shape) — the
    image model is given the satellite crop as the structural reference.
  * Keep proposed elements inside the backyard and scaled to real measurements.
  * Apply the chosen style's materials/plants/mood and the user's vision.

Providers are pluggable via the RENDER_PROVIDER env var (openai | replicate | fal).
With none configured the pipeline runs in DEMO mode: it returns the engineered
prompt and uses the real satellite image as a placeholder "after" so the whole UX
works end-to-end without a paid key. Drop in a key to switch on real renders.
"""
from __future__ import annotations

import os

from styles import get_style


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

# Camera viewpoints the render can be framed from. "hero" is the default: a
# three-quarter aerial-oblique that shows the HOUSE and the full BACKYARD together
# in one natural-daylight frame (what most clients want to see first).
VIEWS = {
    "hero": (
        "Three-quarter aerial-oblique photograph, as if from a drone hovering at "
        "roughly a 30-degree downward angle behind the property: frame the FULL "
        "house (facade and roofline clearly visible) TOGETHER WITH the entire "
        "backyard in a single shot, with natural depth and perspective. The house "
        "and the designed yard must both be clearly visible in the same image."
    ),
    "aerial": (
        "Render from the SAME overhead aerial viewpoint as the reference image "
        "(top-down bird's-eye), so the result aligns 1:1 with the real property."
    ),
    "eye_level": (
        "Ground-level, eye-level photograph taken from within the yard looking "
        "back toward the house, natural human standing perspective (~5.5 ft camera "
        "height), with the house in the background and the designed landscaping in "
        "the foreground and mid-ground."
    ),
}
DEFAULT_VIEW = "hero"


def build_prompt(prop: dict, style_key: str, vision: str,
                 elements: list = None, time_of_day: str = "day",
                 view: str = DEFAULT_VIEW) -> str:
    style = get_style(style_key)
    viewpoint = VIEWS.get(view, VIEWS[DEFAULT_VIEW])
    sizes = prop.get("sizes", {})
    lot = sizes.get("lot_sqft")
    backyard = sizes.get("backyard_sqft")

    scale_bits = []
    if lot:
        scale_bits.append(f"lot ~{lot:,} sq ft")
    if backyard:
        scale_bits.append(f"usable backyard ~{backyard:,} sq ft")
    scale = "; ".join(scale_bits) or "scale taken from the reference image"

    lighting = {
        "day": "bright clear midday daylight, soft natural shadows",
        "dusk": "warm golden-hour dusk light, glowing landscape lighting, "
                "string lights and path uplighting switched on",
        "evening": "evening/night scene, landscape lighting, uplit trees, "
                   "glowing pool and string lights against a dark blue sky",
    }.get(time_of_day, "bright clear midday daylight")

    el_text = ""
    if elements:
        described = []
        for e in elements:
            if not isinstance(e, dict):
                continue
            etype = e.get("type") or e.get("key")
            if not etype:
                continue
            opts = e.get("options") if isinstance(e.get("options"), dict) else {}
            spec = ", ".join(f"{k}: {v}" for k, v in opts.items())
            described.append(str(etype) + (f" ({spec})" if spec else ""))
        if described:
            el_text = "Include these elements: " + "; ".join(described) + ". "

    vision = (vision or "").strip()
    vision_text = f'Client vision: "{vision}". ' if vision else ""

    return (
        "Photorealistic architectural visualization of a designed yard, "
        "rendered ONTO the client's actual property shown in the reference aerial "
        "image. CRITICAL SPATIAL RULES: keep the exact same house, roofline, "
        "garage, existing structures, driveway and walkways, lot shape and "
        "property boundaries as the reference — do not move, cover, or invent any "
        "of them. Never place trees, beds, paths, water features or hardscape on "
        "top of the house, any structure, or the driveway. Keep the driveway and "
        "the path from street to front door fully clear and connected. Place all "
        "new landscaping ONLY on the open ground inside the property lines, set "
        "back from the house and boundaries. "
        f"Real-world scale: {scale}; size every element to real measurements. "
        f"{vision_text}{el_text}"
        f"Overall style: {style['prompt_fragment']}. "
        f"Use materials: {style['materials']}; planting: {style['plants']}. "
        f"Lighting: {lighting}. "
        f"{viewpoint} "
        "Photorealistic, true-to-life materials (real water, grass, wood, stone), "
        "accurate sun shadows, high detail, professional real-estate photography look. "
        "Not a diagram, not clip art, not a flat plan."
    )


def negative_prompt() -> str:
    return ("cartoon, illustration, clip art, flat diagram, blueprint, low detail, "
            "distorted house, wrong proportions, extra buildings, text, watermark, "
            "unrealistic colors")


# ---------------------------------------------------------------------------
# Providers (pluggable)
# ---------------------------------------------------------------------------

def render_status() -> dict:
    """Whether live renders are on (a provider + key are configured) for the UI."""
    import connections
    cfg = connections.get_render_config()
    live = bool(cfg["provider"] and cfg["api_key"])
    return {"live": live, "provider": cfg["provider"] if live else None,
            "mode": "live" if live else "demo"}


def generate(prop: dict, style_key: str, vision: str,
             elements: list = None, time_of_day: str = "day",
             view: str = DEFAULT_VIEW) -> dict:
    """
    Run the render. Returns:
      {demo, provider, prompt, negative, before_url, after_url, view, note}
    In demo mode after_url == the real satellite image (placeholder) and demo=True.
    """
    import connections
    prompt = build_prompt(prop, style_key, vision, elements, time_of_day, view)
    neg = negative_prompt()
    before = prop.get("satellite_url")
    cfg = connections.get_render_config()
    provider, api_key, model = cfg["provider"], cfg["api_key"], cfg["model"]

    if provider and api_key:
        try:
            after = _call_provider(provider, prompt, neg, before, time_of_day, api_key, model)
            return {"demo": False, "provider": provider, "prompt": prompt,
                    "negative": neg, "before_url": before, "after_url": after,
                    "view": view, "note": None}
        except Exception as exc:  # never break the UX on a provider error
            import sys
            print(f"[render] provider '{provider}' failed: {exc}", file=sys.stderr)
            return {"demo": True, "error": True, "provider": provider, "prompt": prompt,
                    "negative": neg, "before_url": before, "after_url": before,
                    "view": view, "note": "Live render failed — showing the satellite as a placeholder. "
                            "Check the server logs and your provider configuration."}

    return {
        "demo": True, "provider": None, "prompt": prompt, "negative": neg,
        "before_url": before, "after_url": before, "view": view,
        "note": ("DEMO MODE — no image-generation API configured. This is the exact "
                 "prompt that would be sent to the image model (conditioned on the "
                 "satellite image). Set RENDER_PROVIDER + an API key to produce the "
                 "real photorealistic render."),
    }


def _call_provider(provider: str, prompt: str, neg: str, image_url: str,
                   time_of_day: str, api_key: str, model: str = "") -> str:
    """
    Drop-in real-render calls. Each conditions on the satellite image so the
    output matches the actual property. Returns the rendered image URL/data URL.
    The api_key/model come from connections.py (admin panel or .env).
    (Executed only when the provider + key are configured.)
    """
    if provider == "openai":
        # Guard against a misconfigured model field (e.g. autofill putting an email
        # there): only honor a value that looks like an OpenAI image model id.
        oa_model = model if (model or "").startswith("gpt-image") else "gpt-image-2"
        return _openai_edit(prompt, image_url, api_key, oa_model)
    if provider == "replicate":
        return _replicate_img2img(prompt, neg, image_url, api_key, model)
    if provider == "fal":
        return _fal_img2img(prompt, neg, image_url, api_key, model)
    raise ValueError(f"unknown provider {provider}")


def _fetch_bytes(url: str) -> bytes:
    # Use the SAME hardened fetch as the rest of the app: https + host allow-list
    # + public-IP check + no redirect following + size cap. No weaker local path.
    from netfetch import safe_image_fetch
    return safe_image_fetch(url)[0]


def _openai_edit(prompt: str, image_url: str, api_key: str, model: str = "gpt-image-2") -> str:
    """OpenAI images edit (gpt-image-2) conditioned on the satellite crop."""
    import base64
    import json
    import urllib.request
    img = _fetch_bytes(image_url)
    boundary = "----landview"
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n',
        f'--{boundary}\r\nContent-Disposition: form-data; name="prompt"\r\n\r\n{prompt}\r\n',
        f'--{boundary}\r\nContent-Disposition: form-data; name="size"\r\n\r\n1024x1024\r\n',
    ]
    body = b"".join(p.encode() for p in parts)
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
             f'filename="site.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()
    body += img + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/edits", data=body,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"OpenAI {e.code}: {detail}") from None
    return "data:image/png;base64," + data["data"][0]["b64_json"]


def _replicate_img2img(prompt: str, neg: str, image_url: str,
                       api_key: str, model: str = "") -> str:
    """Replicate (e.g. SDXL/Flux img2img or ControlNet) conditioned on the image."""
    import json
    import time
    import urllib.request
    token = api_key
    version = model or os.environ.get("REPLICATE_MODEL_VERSION", "")  # chosen model version
    payload = json.dumps({"version": version, "input": {
        "prompt": prompt, "negative_prompt": neg, "image": image_url,
        "prompt_strength": 0.65}}).encode()
    req = urllib.request.Request(
        "https://api.replicate.com/v1/predictions", data=payload,
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        pred = json.loads(r.read().decode())
    get_url = pred["urls"]["get"]
    for _ in range(60):
        with urllib.request.urlopen(urllib.request.Request(
                get_url, headers={"Authorization": f"Token {token}"}), timeout=30) as r:
            pred = json.loads(r.read().decode())
        if pred["status"] == "succeeded":
            out = pred["output"]
            return out[-1] if isinstance(out, list) else out
        if pred["status"] in ("failed", "canceled"):
            raise RuntimeError("replicate prediction failed")
        time.sleep(2)
    raise TimeoutError("replicate timed out")


def _fal_img2img(prompt: str, neg: str, image_url: str,
                 api_key: str, model: str = "") -> str:
    """fal.ai img2img/ControlNet conditioned on the satellite image."""
    import json
    import urllib.request
    model = model or os.environ.get("FAL_MODEL", "fal-ai/flux/dev/image-to-image")
    payload = json.dumps({"prompt": prompt, "image_url": image_url,
                          "strength": 0.65}).encode()
    req = urllib.request.Request(
        f"https://fal.run/{model}", data=payload,
        headers={"Authorization": f"Key {api_key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    imgs = data.get("images") or data.get("image")
    return imgs[0]["url"] if isinstance(imgs, list) else imgs["url"]
