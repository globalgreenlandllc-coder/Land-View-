# Deploying Land-View

Land-View ships as **one Docker service**: the Flask app serves both the API and
the built React SPA on a single port. State (SQLite DB + generated secrets) lives
in `_store/`, so production needs a **persistent disk** mounted there.

## Option A — Render (recommended, one-click)

1. Push to GitHub (already done on `main`).
2. On [Render](https://render.com) → **New → Blueprint** → pick this repo.
   Render reads [`render.yaml`](render.yaml): a Docker web service with a 1 GB disk
   mounted at `/app/_store` and auto-generated `JWT_SECRET` / `LANDVIEW_SECRET`.
3. Deploy. Open the URL, **register the first account** (it becomes admin), then
   add provider keys in **Admin → API connections** (OpenAI for renders, Google
   for geocoding). Keys are encrypted on the persistent disk.

## Option B — any Docker host (Fly.io, Railway, a VM)

```bash
docker build -t land-view .
docker run -p 8000:8000 \
  -e JWT_SECRET=$(openssl rand -hex 32) \
  -e LANDVIEW_SECRET=$(openssl rand -hex 32) \
  -v land_view_store:/app/_store \
  land-view
# open http://localhost:8000
```

## Environment variables

| Var | Purpose |
| --- | --- |
| `JWT_SECRET` | Signs auth tokens. **Set a stable value in prod.** |
| `LANDVIEW_SECRET` | Encrypts stored API keys at rest. **Set a stable value.** |
| `PORT` / `HOST` | Bind address (default `8000` / `0.0.0.0`). |
| `CORS_ORIGINS` | Extra allowed origins (csv) — only if the SPA is on another domain. |
| `OPENAI_API_KEY` + `RENDER_PROVIDER=openai` | Optional: enable real renders via env instead of the admin panel. |
| `GEOCODER=google` + `GEOCODER_KEY` | Optional: Google geocoding via env. |

> Provider keys can be set **either** via env vars **or** in-app (Admin → API
> connections, encrypted on disk). The admin panel takes precedence.

## Notes
- **Persist `_store/`** or you lose accounts + saved designs on each restart.
  (For multi-instance scale, migrate to PostgreSQL — single-parcel geometry needs
  no PostGIS.)
- A live image render takes ~30–60s; the gunicorn worker timeout is set to 180s.
- Local dev is still `./run.sh` (Flask :8000 + Vite :5174).
