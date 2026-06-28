"""
connections.py -- Service abstraction for third-party APIs.

The admin panel configures each *service* (render / geocoding / parcel / mapping)
with a *provider* and an (encrypted) secret. The rest of the app asks this module
for the active config instead of reading env vars directly, so a provider can be
swapped from the admin UI without touching code. Order of precedence:

    1. an api_connections row saved from the admin panel (secret decrypted here)
    2. environment variables (.env) as a fallback

Secrets are encrypted at rest via crypto.py and only ever decrypted in-process;
the admin API returns a masked preview, never the raw key.
"""
from __future__ import annotations

import os

import crypto
import store

# Service catalog surfaced to the admin UI. `wired` marks services that actually
# affect behavior today; the others are stored config for upcoming integrations.
SERVICES = {
    "render": {
        "label": "AI image rendering",
        "providers": ["openai", "replicate", "fal"],
        "secret_label": "API key",
        "endpoint_label": "Model / version (replicate & fal)",
        "wired": True,
    },
    "geocoding": {
        "label": "Geocoding (address → coordinates)",
        "providers": ["nominatim", "google", "mapbox"],
        "secret_label": "API key (not needed for Nominatim)",
        "endpoint_label": "Endpoint (optional)",
        "wired": True,
    },
    "parcel": {
        "label": "Parcel / property data",
        "providers": ["demo", "regrid", "attom"],
        "secret_label": "API key / token (not needed for demo)",
        "endpoint_label": "Base URL (optional)",
        "wired": True,
    },
    "mapping": {
        "label": "Mapping / aerial imagery",
        "providers": ["esri", "mapbox"],
        "secret_label": "Access token (Mapbox; Esri needs none)",
        "endpoint_label": "Style URL (optional)",
        "wired": True,
    },
}

_ENV_KEY = {"openai": "OPENAI_API_KEY", "replicate": "REPLICATE_API_TOKEN", "fal": "FAL_KEY"}


def _mask(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 6:
        return "••••"
    return secret[:3] + "•" * 6 + secret[-3:]


def get_render_config() -> dict:
    """Active render provider config: {provider, api_key, model}. DB then env."""
    row = store.get_connection("render")
    if row is not None and row["provider"]:
        key = crypto.decrypt(row["secret_enc"]) if row["secret_enc"] else ""
        return {"provider": row["provider"], "api_key": key, "model": row["endpoint"] or ""}
    provider = (os.environ.get("RENDER_PROVIDER") or "").lower().strip() or None
    if provider:
        env_name = _ENV_KEY.get(provider)
        return {
            "provider": provider,
            "api_key": os.environ.get(env_name, "") if env_name else "",
            "model": os.environ.get("REPLICATE_MODEL_VERSION")
            or os.environ.get("FAL_MODEL") or "",
        }
    return {"provider": None, "api_key": "", "model": ""}


def get_geocode_config() -> dict:
    """Active geocoder config: {provider, api_key, endpoint}. DB then env."""
    row = store.get_connection("geocoding")
    if row is not None and row["provider"]:
        key = crypto.decrypt(row["secret_enc"]) if row["secret_enc"] else ""
        return {"provider": row["provider"], "api_key": key, "endpoint": row["endpoint"] or ""}
    provider = (os.environ.get("GEOCODER") or "").lower().strip() or "nominatim"
    return {"provider": provider, "api_key": os.environ.get("GEOCODER_KEY", ""), "endpoint": ""}


def get_parcel_config() -> dict:
    """Active parcel provider config: {provider, api_key, endpoint}. DB then env."""
    row = store.get_connection("parcel")
    if row is not None and row["provider"]:
        key = crypto.decrypt(row["secret_enc"]) if row["secret_enc"] else ""
        return {"provider": row["provider"], "api_key": key, "endpoint": row["endpoint"] or ""}
    provider = (os.environ.get("PARCEL_PROVIDER") or "").lower().strip() or "demo"
    return {"provider": provider, "api_key": os.environ.get("PARCEL_API_KEY", ""),
            "endpoint": os.environ.get("PARCEL_API_BASE", "")}


def get_map_config() -> dict:
    """Active mapping config for the client: {provider, token, style}. DB then env."""
    row = store.get_connection("mapping")
    if row is not None and row["provider"]:
        token = crypto.decrypt(row["secret_enc"]) if row["secret_enc"] else ""
        return {"provider": row["provider"], "token": token, "style": row["endpoint"] or ""}
    provider = (os.environ.get("MAP_PROVIDER") or "").lower().strip() or "esri"
    return {"provider": provider, "token": os.environ.get("MAPBOX_TOKEN", ""),
            "style": os.environ.get("MAP_STYLE", "")}


def set_connection(service: str, provider: str, endpoint: str,
                   secret: str | None, actor_id: str = "", actor_email: str = "") -> None:
    """Save/update a service connection. A None/empty secret keeps the existing one."""
    if service not in SERVICES:
        raise ValueError(f"unknown service: {service}")
    if provider not in SERVICES[service]["providers"]:
        raise ValueError(f"unknown provider '{provider}' for service '{service}'")
    secret_enc = crypto.encrypt(secret) if secret else None
    store.upsert_connection(service, provider, endpoint or "", secret_enc, actor_email or actor_id)


def delete_connection(service: str) -> bool:
    return store.delete_connection(service)


def list_public() -> list:
    """Masked view for the admin UI — never exposes raw secrets."""
    saved = {r["service"]: r for r in store.list_connections()}
    out = []
    for service, meta in SERVICES.items():
        row = saved.get(service)
        masked, configured, provider, endpoint, updated = "", False, None, "", None
        if row is not None:
            provider = row["provider"]
            endpoint = row["endpoint"] or ""
            updated = {"at": row["updated_at"], "by": row["updated_by"]}
            if row["secret_enc"]:
                try:
                    masked = _mask(crypto.decrypt(row["secret_enc"]))
                except Exception:
                    masked = "••••"
            configured = bool(provider)
        # Reflect env-based config for render (only if .env actually has a key).
        env_cfg = get_render_config() if service == "render" else None
        env_active = bool(service == "render" and not configured
                          and env_cfg["provider"] and env_cfg["api_key"])
        if env_active:
            provider = env_cfg["provider"]
            masked = _mask(env_cfg["api_key"])
        out.append({
            "service": service,
            "label": meta["label"],
            "providers": meta["providers"],
            "secret_label": meta["secret_label"],
            "endpoint_label": meta["endpoint_label"],
            "wired": meta["wired"],
            "provider": provider,
            "endpoint": endpoint,
            "secret_masked": masked,
            "configured": bool(configured or env_active),
            "source": "database" if configured else ("env" if env_active else None),
            "updated": updated,
        })
    return out
