# Deploying Land-View

Land-View ships as **one Docker service**: the Flask app serves both the API and
the built React SPA on a single port. State (SQLite DB + generated secrets) lives
in `_store/`, so production needs a **persistent disk** mounted there.

## Option A — Vercel (frontend static + Python API function)

Vercel is **serverless**, so there is no local disk: state must live in **Postgres**,
and secrets must be **env vars** (the app handles both automatically).

1. **Create a free Postgres** (e.g. [Neon](https://neon.tech) or Vercel Postgres) and
   copy its connection string.
2. In the Vercel project → **Settings → Environment Variables**, add:
   | Name | Value |
   | --- | --- |
   | `DATABASE_URL` | your Postgres URL (`postgres://…`) — switches storage to Postgres |
   | `JWT_SECRET` | any long random string (`openssl rand -hex 32`) |
   | `LANDVIEW_SECRET` | another long random string |
   | `OPENAI_API_KEY` + `RENDER_PROVIDER=openai` | optional: real renders |
   | `GEOCODER=google` + `GEOCODER_KEY` | optional: Google geocoding |
3. **Redeploy.** `vercel.json` builds the SPA (`@vercel/static-build`) and runs the
   API as a Python function (`/api/*`, 60 s max for renders). Tables auto-create on
   first request. Open the URL → register the first account (admin) → optionally add
   keys in Admin → API connections.

> Without `DATABASE_URL` the function falls back to SQLite on an ephemeral disk and
> **data won't persist** — set it. Renders must finish within Vercel's 60 s function
> limit (Pro allows more).

## Option B — Render (one-click, persistent disk)

1. Push to GitHub (already done on `main`).
2. On [Render](https://render.com) → **New → Blueprint** → pick this repo.
   Render reads [`render.yaml`](render.yaml): a Docker web service with a 1 GB disk
   mounted at `/app/_store` and auto-generated `JWT_SECRET` / `LANDVIEW_SECRET`.
3. Deploy. Open the URL, **register the first account** (it becomes admin), then
   add provider keys in **Admin → API connections** (OpenAI for renders, Google
   for geocoding). Keys are encrypted on the persistent disk.

## Option C — any Docker host (Fly.io, Railway, a VM)

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
