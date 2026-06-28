# Land-View

**Parcel & landscape design platform.** Search a real parcel by address / APN /
coordinates, view its boundary and attributes on an interactive map, design the
landscape on a drag-and-drop canvas, and generate AI photorealistic renders of the
property — all behind email/password accounts with a full admin panel.

> Built as a single Python (Flask) backend + React (Vite) frontend, **stdlib-only
> on the backend** (no extra Python packages to install). Real third-party APIs
> (image rendering, parcel data, Mapbox) are optional and pluggable from the
> in-app Admin → API Connections panel.

## Quick start

```bash
./run.sh                 # API on :8000, UI on :5174 — open http://localhost:5174
```

Or separately:

```bash
pip install -r requirements.txt
python server.py                          # API on :8000
cd web && npm install && npm run dev      # UI on :5174
```

The **first account you register becomes the admin**. Everything works with no API
keys: geocoding (OpenStreetMap Nominatim), satellite (Esri World Imagery), an
interactive map (MapLibre GL over Esri tiles), and **demo parcel data** with
estimated boundaries. Add real provider keys in the admin panel to upgrade.

## What it does

### User
- **Accounts** — email/password registration & login (JWT access + refresh tokens).
- **Parcel search** — by **address**, **APN**, or **coordinates** (`lat, lng`).
- **Parcel view** — owner, APN, zoning, assessed value, lot size, dimensions, with
  the boundary drawn on an **interactive satellite map** (MapLibre GL).
- **Design canvas** — drag-and-drop trees, plants, lawns, patios, pools, paths,
  fences, structures, lighting onto the real parcel; boundary overlay + scale bar.
- **Measurement tools** — distance & area, both on the map and the canvas.
- **AI render** — photorealistic visualization conditioned on the real satellite
  image, in 10 style presets and 3 camera views (house+yard / top-down / eye-level).
- **Designs** — save / reload / export image + client PDF, scoped to your account.

### Admin (role-gated)
- **Analytics** — users, active/suspended, designs, searches, renders, logins.
- **User management** — suspend / reactivate / promote / delete.
- **API Connection Manager** — configure render / geocoding / parcel / mapping
  providers; **keys encrypted at rest**, shown only masked, swappable without code.
- **Audit log** — every login, search, render, and admin action.

## Architecture

| File | Role |
| --- | --- |
| `server.py` | Flask API: auth, parcel, render, designs, admin, image proxy |
| `auth.py` | Password hashing (PBKDF2), JWT access/refresh, `@require_auth`/`@require_admin` |
| `crypto.py` | Authenticated encryption (encrypt-then-MAC) for stored API keys |
| `store.py` | SQLite: users, designs (owner-scoped), api_connections, audit_log |
| `connections.py` | Service abstraction — active provider config (DB → env fallback) |
| `parcel.py` | Parcel provider abstraction: demo (no key) + Regrid / ATTOM |
| `geo.py` | Geocode (Nominatim), satellite (Esri), scale & size estimates |
| `render.py` | Property-accurate prompt + pluggable image provider (demo until keyed) |
| `cost.py`, `pdf.py`, `styles.py`, `elements.py` | Cost estimate, client PDF, presets, catalog |
| `web/` | React + Vite UI (auth, map, canvas, admin), MapLibre GL |

## API integration

All third-party providers are configured from **Admin → API Connections** (stored
encrypted in the DB) or via environment variables as a fallback. DB config wins.

| Service | Providers | Needs key | Status |
| --- | --- | --- | --- |
| AI image rendering | openai / replicate / fal | yes | live |
| Parcel / property data | demo / regrid / attom | demo: no | live (demo default) |
| Mapping / aerial | esri / mapbox | esri: no | live (esri default) |
| Geocoding | nominatim / mapbox / google | nominatim: no | stored (Nominatim today) |

See `.env.example` for environment-variable setup and the two server secrets
(`JWT_SECRET`, `LANDVIEW_SECRET`) to set in production.

### REST endpoints (summary)

```
POST /api/auth/register | /login | /refresh        GET /api/auth/me
GET  /api/parcel?q=&kind=address|apn|coords        GET /api/map-config
POST /api/render                                    GET/POST/DELETE /api/designs[/<id>]
GET  /api/styles | /api/elements                    POST /api/cost | /api/pdf
# admin (role-gated)
GET    /api/admin/users       PATCH/DELETE /api/admin/users/<id>
GET    /api/admin/connections PUT/DELETE   /api/admin/connections/<service>
GET    /api/admin/analytics   GET /api/admin/audit
```

> Demo parcel data and AI renders are visualization aids, not a survey or a
> construction document. Connect Regrid/ATTOM for authoritative parcels and an
> image provider for real renders.
