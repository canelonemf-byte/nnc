"""TLE / satellite pass: Celestrak GP JSON + skyfield SGP4."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from skyfield.api import EarthSatellite, Loader, wgs84

from .config import CACHE_DIR, DATA_DIR, STATION, TLE_CACHE_S, USER_AGENT

CACHE_FILE = CACHE_DIR / "tle_25544.json"
TLE_TEXT_FILE = CACHE_DIR / "tle_25544.txt"
MADRID = ZoneInfo("Europe/Madrid")
LOADER = Loader(str(DATA_DIR / "skyfield"))


def _now_madrid_iso() -> str:
    return datetime.now(MADRID).isoformat(timespec="seconds")


def fetch_celestrak_tle(norad: int = 25544, force: bool = False) -> dict[str, Any]:
    if CACHE_FILE.exists() and not force:
        cached = json.loads(CACHE_FILE.read_text())
        age = time.time() - cached.get("_cached_at", 0)
        if age < TLE_CACHE_S:
            cached["cache_hit"] = True
            cached["cache_age_s"] = round(age, 1)
            return cached

    url_json = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=json"
    url_tle = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=tle"
    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        r_json = client.get(url_json)
        r_tle = client.get(url_tle)
    if r_json.status_code != 200 or r_tle.status_code != 200:
        # fall back to local
        if CACHE_FILE.exists():
            cached = json.loads(CACHE_FILE.read_text())
            cached["ok"] = True
            cached["stale"] = True
            cached["fuente"] = "celestrak|local_stale"
            cached["http_status_json"] = r_json.status_code
            cached["http_status_tle"] = r_tle.status_code
            return cached
        return {
            "ok": False,
            "http_status_json": r_json.status_code,
            "http_status_tle": r_tle.status_code,
            "fuente": "celestrak",
            "error": "fetch failed and no local TLE",
        }

    gp = r_json.json()
    tle_text = r_tle.text.strip()
    TLE_TEXT_FILE.write_text(tle_text + "\n")
    out = {
        "ok": True,
        "http_status": 200,
        "fuente": "celestrak",
        "norad": norad,
        "gp": gp[0] if isinstance(gp, list) and gp else gp,
        "tle_text": tle_text,
        "fetched_at_madrid": _now_madrid_iso(),
        "_cached_at": time.time(),
        "cache_hit": False,
    }
    CACHE_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def _satellite_from_cache(norad: int = 25544) -> tuple[EarthSatellite, dict[str, Any]]:
    meta = fetch_celestrak_tle(norad=norad)
    if not meta.get("ok"):
        raise RuntimeError(meta.get("error") or "TLE unavailable")
    text = meta.get("tle_text") or TLE_TEXT_FILE.read_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    ts = LOADER.timescale()
    if len(lines) >= 3:
        sat = EarthSatellite(lines[1], lines[2], lines[0].strip(), ts)
    else:
        sat = EarthSatellite(lines[0], lines[1], f"NORAD-{norad}", ts)
    return sat, meta


def predict_pass(
    norad: int = 25544,
    hours: float = 24.0,
    min_el_deg: float = 10.0,
    lat: float | None = None,
    lon: float | None = None,
    h_m: float | None = None,
) -> dict[str, Any]:
    lat = STATION["lat_deg"] if lat is None else lat
    lon = STATION["lon_deg"] if lon is None else lon
    h_m = STATION["h_m"] if h_m is None else h_m
    sat, meta = _satellite_from_cache(norad)
    ts = LOADER.timescale()
    station = wgs84.latlon(lat, lon, elevation_m=h_m)
    t0 = ts.now()
    t1 = ts.utc(t0.utc_datetime() + timedelta(hours=hours))
    times, events = sat.find_events(station, t0, t1, altitude_degrees=min_el_deg)
    names = {0: "rise", 1: "culminate", 2: "set"}
    events_out = []
    first_culm = None
    for ti, ei in zip(times, events):
        top = (sat - station).at(ti)
        alt, az, dist = top.altaz()
        utc_iso = ti.utc_iso()
        # convert to Madrid
        dt_utc = ti.utc_datetime().replace(tzinfo=timezone.utc)
        madrid_iso = dt_utc.astimezone(MADRID).isoformat(timespec="seconds")
        row = {
            "event": names.get(int(ei), str(ei)),
            "t_utc": utc_iso,
            "t_madrid": madrid_iso,
            "az_deg": round(float(az.degrees), 3),
            "el_deg": round(float(alt.degrees), 3),
            "range_km": round(float(dist.km), 2),
        }
        events_out.append(row)
        if int(ei) == 1 and first_culm is None:
            first_culm = row

    # topocentric now
    now_top = (sat - station).at(t0)
    n_alt, n_az, n_dist = now_top.altaz()
    return {
        "ok": True,
        "modo": "experimento",
        "norad": norad,
        "nombre": (meta.get("gp") or {}).get("OBJECT_NAME", ""),
        "tle_epoch": (meta.get("gp") or {}).get("EPOCH", ""),
        "tle_fuente": meta.get("fuente", ""),
        "tle_http_status": meta.get("http_status", meta.get("http_status_json", "")),
        "station": {
            "lat_deg": lat,
            "lon_deg": lon,
            "h_m": h_m,
            "coord_status": STATION["coord_status"],
        },
        "min_el_deg": min_el_deg,
        "now": {
            "t_utc": t0.utc_iso(),
            "az_deg": round(float(n_az.degrees), 3),
            "el_deg": round(float(n_alt.degrees), 3),
            "range_km": round(float(n_dist.km), 2),
            "above_horizon": bool(float(n_alt.degrees) > 0),
        },
        "next_culmination": first_culm or {},
        "events": events_out,
        "fetched_at_madrid": _now_madrid_iso(),
        "equations": "SGP4 via skyfield EarthSatellite.find_events; topocentric altaz",
    }


def satellite_azel_at(
    t_utc: datetime,
    norad: int = 25544,
    lat: float | None = None,
    lon: float | None = None,
    h_m: float | None = None,
) -> dict[str, Any]:
    lat = STATION["lat_deg"] if lat is None else lat
    lon = STATION["lon_deg"] if lon is None else lon
    h_m = STATION["h_m"] if h_m is None else h_m
    sat, meta = _satellite_from_cache(norad)
    ts = LOADER.timescale()
    if t_utc.tzinfo is None:
        t_utc = t_utc.replace(tzinfo=timezone.utc)
    t = ts.from_datetime(t_utc.astimezone(timezone.utc))
    station = wgs84.latlon(lat, lon, elevation_m=h_m)
    alt, az, dist = (sat - station).at(t).altaz()
    return {
        "norad": norad,
        "t_utc": t.utc_iso(),
        "az_deg": float(az.degrees),
        "el_deg": float(alt.degrees),
        "range_km": float(dist.km),
        "tle_fuente": meta.get("fuente", ""),
    }
