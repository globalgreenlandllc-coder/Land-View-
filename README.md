# Land-View

AI backyard designer for landscape professionals. Enter a client's address →
pull real satellite imagery and real-world scale → pick a design style and
describe the vision → generate a **photorealistic backyard render conditioned on
the client's actual property** → present before/after and export.

> **Phase 1 (this build):** address → satellite → estimated sizes → style preset →
> vision → engineered render prompt → before/after + export. The render step runs
> in **demo mode** until an image-generation API is connected (see below).

## Quick start

```bash
./run.sh                 # then open http://localhost:5174  (Ctrl+C stops both)
```

Or separately:

```bash
pip install -r requirements.txt
python server.py                          # API on :8000
cd web && npm install && npm run dev      # UI on :5174
```

No API keys are needed to run Phase 1 — geocoding (OpenStreetMap Nominatim) and
satellite imagery (Esri World Imagery) are free/no-key.

## Turning on real photorealistic renders

The render pipeline (`render.py`) is engineered to condition the image model on the
real satellite image so the output keeps the **same house and lot**. To switch from
demo to real renders, set an environment variable for one provider and its key:

```bash
export RENDER_PROVIDER=openai     # gpt-image-1 (image edit)
export OPENAI_API_KEY=sk-...

# or
export RENDER_PROVIDER=replicate  # SDXL/Flux img2img or ControlNet
export REPLICATE_API_TOKEN=...
export REPLICATE_MODEL_VERSION=<version>

# or
export RENDER_PROVIDER=fal        # Flux image-to-image
export FAL_KEY=...
```

Per-image cost applies. The provider call code is in `render.py` (`_call_provider`).

## Architecture

| File | Role |
| --- | --- |
| `geo.py` | Geocode (Nominatim), satellite (Esri), real-world scale + approximate lot/house/backyard sizes (OSM Overpass footprint best-effort) |
| `styles.py` | 8 named style presets driving materials/plants/mood |
| `render.py` | Engineers the property-accurate photorealistic prompt; pluggable image provider (demo until a key is set) |
| `server.py` | Flask API: `/api/property`, `/api/styles`, `/api/render`, allow-listed image proxy |
| `web/` | React + Vite UI (mobile-friendly) |

## Roadmap

- **Phase 2:** tap-to-edit elements (add/move/resize/swap), per-element materials
  (pool shape, deck wood, fence type…), re-render on change, save/reload designs.
- **Phase 3:** PDF client presentations, day/dusk/evening render modes (prompt
  already supports it), rough cost estimator, deeper mobile polish.
- Precise lot boundaries via a parcel API (e.g. Regrid) and ML house-footprint
  detection.

> Renders are an AI visualization aid, not a construction document or survey.
