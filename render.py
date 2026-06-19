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

def build_prompt(prop: dict, style_key: str, vision: str,
                 elements: list = None, time_of_day: str = "day") -> str:
    style = get_style(style_key)
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
            spec = ", ".join(f"{k}: {v}" for k, v in (e.get("options") or {}).items())
            described.append(e["type"] + (f" ({spec})" if spec else ""))
        el_text = "Include these elements: " + "; ".join(described) + ". "

    vision = (vision or "").strip()
    vision_text = f'Client vision: "{vision}". ' if vision else ""

    return (
        "Photorealistic architectural visualization of a designed backyard, "
        "rendered ONTO the client's actual property shown in the reference aerial "
        "image. CRITICAL: keep the exact same house, roofline, lot shape and "
        "property boundaries as the reference; do not invent a different house or "
        "lot. Place all new landscaping only within the open backyard area, with "
        "realistic setbacks from the house and property lines. "
        f"Real-world scale: {scale}; size every element to real measurements. "
        f"{vision_text}{el_text}"
        f"Overall style: {style['prompt_fragment']}. "
        f"Use materials: {style['materials']}; planting: {style['plants']}. "
        f"Lighting: {lighting}. "
        "Photorealistic, true-to-life materials (real water, grass, wood, stone), "
        "accurate shadows and reflections, high detail, professional landscape "
        "photography, believable perspective. Not a diagram, not clip art, not a "
        "flat plan."
    )


def negative_prompt() -> str:
    return ("cartoon, illustration, clip art, flat diagram, blueprint, low detail, "
            "distorted house, wrong proportions, extra buildings, text, watermark, "
            "unrealistic colors")


# ---------------------------------------------------------------------------
# Providers (pluggable)
# ---------------------------------------------------------------------------

def _provider() -> str | None:
    p = (os.environ.get("RENDER_PROVIDER") or "").lower().strip()
    return p or None


def _provider_configured(p: str) -> bool:
    return {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "replicate": bool(os.environ.get("REPLICATE_API_TOKEN")),
        "fal": bool(os.environ.get("FAL_KEY")),
    }.get(p, False)


def generate(prop: dict, style_key: str, vision: str,
             elements: list = None, time_of_day: str = "day") -> dict:
    """
    Run the render. Returns:
      {demo, provider, prompt, negative, before_url, after_url, note}
    In demo mode after_url == the real satellite image (placeholder) and demo=True.
    """
    prompt = build_prompt(prop, style_key, vision, elements, time_of_day)
    neg = negative_prompt()
    before = prop.get("satellite_url")
    provider = _provider()

    if provider and _provider_configured(provider):
        try:
            after = _call_provider(provider, prompt, neg, before, time_of_day)
            return {"demo": False, "provider": provider, "prompt": prompt,
                    "negative": neg, "before_url": before, "after_url": after,
                    "note": None}
        except Exception as exc:  # never break the UX on a provider error
            return {"demo": True, "provider": provider, "prompt": prompt,
                    "negative": neg, "before_url": before, "after_url": before,
                    "note": f"Render provider error ({exc}); showing placeholder."}

    return {
        "demo": True, "provider": None, "prompt": prompt, "negative": neg,
        "before_url": before, "after_url": before,
        "note": ("DEMO MODE — no image-generation API configured. This is the exact "
                 "prompt that would be sent to the image model (conditioned on the "
                 "satellite image). Set RENDER_PROVIDER + an API key to produce the "
                 "real photorealistic render."),
    }


def _call_provider(provider: str, prompt: str, neg: str, image_url: str,
                   time_of_day: str) -> str:
    """
    Drop-in real-render calls. Each conditions on the satellite image so the
    output matches the actual property. Returns the rendered image URL/data URL.
    (Executed only when the provider + key are configured.)
    """
    if provider == "openai":
        return _openai_edit(prompt, image_url)
    if provider == "replicate":
        return _replicate_img2img(prompt, neg, image_url)
    if provider == "fal":
        return _fal_img2img(prompt, neg, image_url)
    raise ValueError(f"unknown provider {provider}")


def _fetch_bytes(url: str) -> bytes:
    import urllib.request
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def _openai_edit(prompt: str, image_url: str) -> str:
    """OpenAI images edit (gpt-image-1) conditioned on the satellite crop."""
    import base64
    import json
    import urllib.request
    img = _fetch_bytes(image_url)
    boundary = "----landview"
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\ngpt-image-1\r\n',
        f'--{boundary}\r\nContent-Disposition: form-data; name="prompt"\r\n\r\n{prompt}\r\n',
        f'--{boundary}\r\nContent-Disposition: form-data; name="size"\r\n\r\n1024x1024\r\n',
    ]
    body = b"".join(p.encode() for p in parts)
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
             f'filename="site.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()
    body += img + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/edits", data=body,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    return "data:image/png;base64," + data["data"][0]["b64_json"]


def _replicate_img2img(prompt: str, neg: str, image_url: str) -> str:
    """Replicate (e.g. SDXL/Flux img2img or ControlNet) conditioned on the image."""
    import json
    import time
    import urllib.request
    token = os.environ["REPLICATE_API_TOKEN"]
    version = os.environ.get("REPLICATE_MODEL_VERSION", "")  # set to your chosen model
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


def _fal_img2img(prompt: str, neg: str, image_url: str) -> str:
    """fal.ai img2img/ControlNet conditioned on the satellite image."""
    import json
    import urllib.request
    model = os.environ.get("FAL_MODEL", "fal-ai/flux/dev/image-to-image")
    payload = json.dumps({"prompt": prompt, "image_url": image_url,
                          "strength": 0.65}).encode()
    req = urllib.request.Request(
        f"https://fal.run/{model}", data=payload,
        headers={"Authorization": f"Key {os.environ['FAL_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    imgs = data.get("images") or data.get("image")
    return imgs[0]["url"] if isinstance(imgs, list) else imgs["url"]
