"""Meteo client: Open-Meteo → MET Norway → stale cache."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import CACHE_DIR, METEO_CACHE_S, STATION, USER_AGENT

CACHE_FILE = CACHE_DIR / "meteo.json"
MADRID = ZoneInfo("Europe/Madrid")


def _now_iso() -> str:
    return datetime.now(MADRID).isoformat(timespec="seconds")


def _load_cache() -> dict[str, Any] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return None


def _save_cache(payload: dict[str, Any]) -> None:
    CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


MAX_RETRY_WAIT_S = 16.0
MAX_TOTAL_WAIT_S = 30.0


def _parse_retry_after(resp: httpx.Response) -> float | None:
    """Retry-After as seconds or HTTP-date; clamped to [0, MAX_RETRY_WAIT_S]."""
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        v = float(ra)
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime
            v = (parsedate_to_datetime(ra) - datetime.now(timezone.utc)).total_seconds()
        except Exception:  # noqa: BLE001
            return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return max(0.0, min(v, MAX_RETRY_WAIT_S))


def _fetch_open_meteo(client: httpx.Client, lat: float, lon: float) -> dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "cloud_cover,visibility,wind_speed_10m,wind_direction_10m",
        "timezone": "Europe/Madrid",
    }
    last_err: str = ""
    waited = 0.0
    status: Any = ""
    for attempt in range(4):
        try:
            resp = client.get(url, params=params)
        except httpx.HTTPError as e:
            return {"ok": False, "http_status": f"error:{type(e).__name__}", "fuente": "open_meteo", "error": str(e)[:200]}
        status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            cur = data.get("current") or {}
            return {
                "ok": True,
                "http_status": 200,
                "fuente": "open_meteo",
                "naturaleza": "modelo_pronostico_no_observacion",
                "cloud_cover_pct": cur.get("cloud_cover"),
                "visibility_m": cur.get("visibility"),
                "wind_speed_10m": cur.get("wind_speed_10m"),
                "wind_speed_unit": (data.get("current_units") or {}).get("wind_speed_10m", "km/h"),
                "wind_direction_10m_deg": cur.get("wind_direction_10m"),
                "api_time": cur.get("time") or "",
                "fetched_at_madrid": _now_iso(),
                "raw_keys": list(cur.keys()),
            }
        if resp.status_code == 429:
            delay = _parse_retry_after(resp)
            if delay is None:
                delay = float(min(2 ** attempt, 16))
            if waited + delay > MAX_TOTAL_WAIT_S or attempt == 3:
                last_err = f"429 budget agotado tras {waited:.0f}s"
                break
            time.sleep(delay)
            waited += delay
            last_err = f"429 after attempt {attempt}"
            continue
        last_err = f"HTTP {resp.status_code}"
        break
    return {"ok": False, "http_status": status, "fuente": "open_meteo", "error": last_err, "waited_s": waited}


def _fetch_met_norway(client: httpx.Client, lat: float, lon: float) -> dict[str, Any]:
    url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    try:
        resp = client.get(url, params={"lat": round(lat, 4), "lon": round(lon, 4)}, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as e:
        return {"ok": False, "http_status": f"error:{type(e).__name__}", "fuente": "met_norway", "error": str(e)[:200]}
    if resp.status_code != 200:
        return {"ok": False, "http_status": resp.status_code, "fuente": "met_norway", "error": resp.text[:200]}
    data = resp.json()
    ts0 = ((data.get("properties") or {}).get("timeseries") or [{}])[0]
    details = ((ts0.get("data") or {}).get("instant") or {}).get("details") or {}
    # wind_speed in m/s → km/h for consistency
    ws_ms = details.get("wind_speed")
    ws_kmh = None if ws_ms is None else round(float(ws_ms) * 3.6, 2)
    return {
        "ok": True,
        "http_status": 200,
        "fuente": "met_norway",
        "cloud_cover_pct": details.get("cloud_area_fraction"),
        "visibility_m": None,  # not in compact endpoint
        "visibility_note": "PENDIENTE_DE_VERIFICACION (compact endpoint sin visibility)",
        "wind_speed_10m": ws_kmh,
        "wind_speed_unit": "km/h",
        "wind_direction_10m_deg": details.get("wind_from_direction"),
        "api_time": ts0.get("time") or "",
        "fetched_at_madrid": _now_iso(),
    }


def get_meteo(lat: float | None = None, lon: float | None = None, force: bool = False) -> dict[str, Any]:
    lat = STATION["lat_deg"] if lat is None else lat
    lon = STATION["lon_deg"] if lon is None else lon
    cached = _load_cache()
    if cached and not force:
        age = time.time() - cached.get("_cached_at", 0)
        if age < METEO_CACHE_S and cached.get("ok"):
            out = dict(cached)
            out["cache_hit"] = True
            out["cache_age_s"] = round(age, 1)
            return out

    with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), headers={"User-Agent": USER_AGENT}) as client:
        result = _fetch_open_meteo(client, lat, lon)
        errors = []
        if not result.get("ok"):
            errors.append({"fuente": "open_meteo", "http_status": result.get("http_status"), "error": result.get("error", "")})
            result = _fetch_met_norway(client, lat, lon)
            if not result.get("ok"):
                errors.append({"fuente": "met_norway", "http_status": result.get("http_status"), "error": result.get("error", "")})
        if not result.get("ok") and cached:
            stale = dict(cached)
            stale["ok"] = True
            stale["stale"] = True
            stale["fuente"] = f"{cached.get('fuente', 'cache')}|stale_cache"
            stale["cache_age_s"] = round(time.time() - cached.get("_cached_at", 0), 1)
            stale["original_fetched_at_madrid"] = cached.get("fetched_at_madrid", "")
            stale["cache_hit"] = True
            stale["errores_fuentes"] = errors
            return stale

    result["_cached_at"] = time.time()
    result["cache_hit"] = False
    if result.get("ok"):
        _save_cache(result)
    return result
