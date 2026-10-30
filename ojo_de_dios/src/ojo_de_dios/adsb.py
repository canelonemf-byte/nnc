"""ADS-B clients: adsb.lol → OpenSky → airplanes.live."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import CACHE_DIR, STATION, USER_AGENT
from .math_geo import bearing_deg, elevation_from_range_alt_deg, haversine_km

CACHE_FILE = CACHE_DIR / "adsb.json"
MADRID = ZoneInfo("Europe/Madrid")


def _now_madrid() -> str:
    return datetime.now(MADRID).isoformat(timespec="seconds")


def _normalize_aircraft(raw: dict[str, Any], station_lat: float, station_lon: float, fuente: str) -> dict[str, Any]:
    lat = raw.get("lat")
    lon = raw.get("lon")
    if lat is None or lon is None:
        return {}
    alt = raw.get("alt_baro", raw.get("alt_geom", raw.get("baro_altitude")))
    on_ground = raw.get("on_ground")
    if alt == "ground":
        alt_ft = 0.0
        on_ground = True
    else:
        try:
            alt_ft = float(alt) if alt is not None else None
        except (TypeError, ValueError):
            alt_ft = None
    dist_km = haversine_km(station_lat, station_lon, float(lat), float(lon))
    az = bearing_deg(station_lat, station_lon, float(lat), float(lon))
    el = None
    if alt_ft is not None and not on_ground:
        el = elevation_from_range_alt_deg(dist_km * 1000.0, alt_ft * 0.3048)
    flight = (raw.get("flight") or raw.get("callsign") or "").strip()
    return {
        "hex": (raw.get("hex") or raw.get("icao24") or "").strip().lower(),
        "flight": flight,
        "lat": float(lat),
        "lon": float(lon),
        "alt_ft": alt_ft,
        "on_ground": bool(on_ground) if on_ground is not None else False,
        "gs_kt": raw.get("gs", raw.get("velocity")),
        "track_deg": raw.get("track", raw.get("true_track")),
        "dist_km": round(dist_km, 3),
        "az_deg": round(az, 3),
        "el_deg": None if el is None else round(el, 3),
        "fuente": fuente,
    }


def _fetch_adsb_lol(client: httpx.Client, lat: float, lon: float, radius_nm: float) -> dict[str, Any]:
    url = f"https://api.adsb.lol/v2/point/{lat}/{lon}/{int(radius_nm)}"
    resp = client.get(url)
    if resp.status_code != 200:
        return {"ok": False, "http_status": resp.status_code, "fuente": "adsb_lol", "aircraft": []}
    data = resp.json()
    acs = []
    for raw in data.get("ac") or []:
        n = _normalize_aircraft(raw, lat, lon, "adsb_lol")
        if n:
            acs.append(n)
    return {
        "ok": True,
        "http_status": 200,
        "fuente": "adsb_lol",
        "aircraft": acs,
        "count": len(acs),
        "fetched_at_madrid": _now_madrid(),
    }


def _fetch_opensky(client: httpx.Client, lat: float, lon: float, radius_nm: float) -> dict[str, Any]:
    # approximate bounding box: 1 deg lat ~ 111 km; 1 nm = 1.852 km
    ddeg = (radius_nm * 1.852) / 111.0
    params = {
        "lamin": lat - ddeg,
        "lamax": lat + ddeg,
        "lomin": lon - ddeg,
        "lomax": lon + ddeg,
    }
    resp = client.get("https://opensky-network.org/api/states/all", params=params)
    if resp.status_code != 200:
        return {"ok": False, "http_status": resp.status_code, "fuente": "opensky", "aircraft": []}
    data = resp.json()
    acs = []
    for s in data.get("states") or []:
        # icao24, callsign, origin_country, time_position, last_contact,
        # longitude, latitude, baro_altitude, on_ground, velocity, true_track, ...
        raw = {
            "icao24": s[0],
            "callsign": (s[1] or "").strip(),
            "lon": s[5],
            "lat": s[6],
            "baro_altitude": None if s[7] is None else float(s[7]) / 0.3048,  # m → ft
            "on_ground": s[8],
            "velocity": None if s[9] is None else float(s[9]) * 1.94384,  # m/s → kt
            "true_track": s[10],
        }
        n = _normalize_aircraft(raw, lat, lon, "opensky")
        if n:
            acs.append(n)
    return {
        "ok": True,
        "http_status": 200,
        "fuente": "opensky",
        "aircraft": acs,
        "count": len(acs),
        "fetched_at_madrid": _now_madrid(),
        "opensky_time": data.get("time"),
    }


def _fetch_airplanes_live(client: httpx.Client, lat: float, lon: float, radius_nm: float) -> dict[str, Any]:
    url = f"https://api.airplanes.live/v2/point/{lat}/{lon}/{int(radius_nm)}"
    resp = client.get(url)
    if resp.status_code != 200:
        return {
            "ok": False,
            "http_status": resp.status_code,
            "fuente": "airplanes_live",
            "aircraft": [],
            "error": resp.text[:200],
        }
    data = resp.json()
    acs = []
    for raw in data.get("ac") or []:
        n = _normalize_aircraft(raw, lat, lon, "airplanes_live")
        if n:
            acs.append(n)
    return {
        "ok": True,
        "http_status": 200,
        "fuente": "airplanes_live",
        "aircraft": acs,
        "count": len(acs),
        "fetched_at_madrid": _now_madrid(),
    }


def get_adsb(lat: float | None = None, lon: float | None = None, radius_nm: float = 50.0, force: bool = False) -> dict[str, Any]:
    lat = STATION["lat_deg"] if lat is None else lat
    lon = STATION["lon_deg"] if lon is None else lon
    if CACHE_FILE.exists() and not force:
        cached = json.loads(CACHE_FILE.read_text())
        age = time.time() - cached.get("_cached_at", 0)
        if age < 30 and cached.get("ok"):
            cached = dict(cached)
            cached["cache_hit"] = True
            cached["cache_age_s"] = round(age, 1)
            return cached

    with httpx.Client(timeout=25.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        result = _fetch_adsb_lol(client, lat, lon, radius_nm)
        fallbacks = [{"fuente": "adsb_lol", "http_status": result.get("http_status"), "ok": result.get("ok")}]
        if not result.get("ok"):
            os_res = _fetch_opensky(client, lat, lon, radius_nm)
            fallbacks.append({"fuente": "opensky", "http_status": os_res.get("http_status"), "ok": os_res.get("ok")})
            if os_res.get("ok"):
                result = os_res
            else:
                al = _fetch_airplanes_live(client, lat, lon, radius_nm)
                fallbacks.append({"fuente": "airplanes_live", "http_status": al.get("http_status"), "ok": al.get("ok")})
                result = al

    result["fallbacks_tried"] = fallbacks if "fallbacks" not in result else result.get("fallbacks_tried", fallbacks)
    # Always record that we tried adsb.lol first when ok
    if result.get("fuente") == "adsb_lol":
        result["fallbacks_tried"] = [{"fuente": "adsb_lol", "http_status": 200, "ok": True}]
    result["_cached_at"] = time.time()
    result["cache_hit"] = False
    result["station"] = {"lat_deg": lat, "lon_deg": lon, "coord_status": STATION["coord_status"]}
    result["radius_nm"] = radius_nm
    if result.get("ok"):
        result["aircraft"] = sorted(result.get("aircraft") or [], key=lambda a: a.get("dist_km") or 1e9)
        CACHE_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def crosscheck(
    t_iso: str,
    az_deg: float,
    el_deg: float,
    radius_nm: float = 50.0,
    sep_deg_max: float = 0.5,
    dt_s_max: float = 5.0,
) -> dict[str, Any]:
    from .math_geo import angular_sep_azel_deg

    snap = get_adsb(radius_nm=radius_nm)
    matches = []
    for ac in snap.get("aircraft") or []:
        if ac.get("el_deg") is None or ac.get("on_ground"):
            continue
        sep = angular_sep_azel_deg(az_deg, el_deg, ac["az_deg"], ac["el_deg"])
        row = {
            **ac,
            "sep_deg": round(sep, 4),
            "within_cone": sep < sep_deg_max,
            "dt_s": "PENDIENTE_DE_VERIFICACION",  # snapshot time vs detection time needs synced clocks
            "dt_note": f"threshold ±{dt_s_max}s; station GNSS/NTP={False}",
        }
        if sep < sep_deg_max:
            matches.append(row)
    matches.sort(key=lambda r: r["sep_deg"])
    return {
        "ok": snap.get("ok", False),
        "fuente": snap.get("fuente", ""),
        "http_status": snap.get("http_status", ""),
        "fetched_at_madrid": snap.get("fetched_at_madrid", ""),
        "query": {"t": t_iso, "az_deg": az_deg, "el_deg": el_deg, "sep_deg_max": sep_deg_max},
        "matches": matches,
        "nearest_airborne": [
            a for a in (snap.get("aircraft") or [])
            if not a.get("on_ground") and a.get("el_deg") is not None and (a.get("alt_ft") or 0) > 0 and (a.get("el_deg") or -1) > 0
        ][:5],
        "ezy95fn_present": any(
            "EZY95FN" in (a.get("flight") or "").upper().replace(" ", "") for a in (snap.get("aircraft") or [])
        ),
    }
