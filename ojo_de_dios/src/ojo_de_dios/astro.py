"""Bright body (Sun/Moon/planets) ephemeris check via skyfield + de421."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from skyfield.api import Loader, wgs84

from .config import DATA_DIR, STATION
from .math_geo import angular_sep_azel_deg

LOADER = Loader(str(DATA_DIR / "skyfield"))
BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter barycenter", "saturn barycenter")


def _ephemeris():
    # download once into data/skyfield
    return LOADER("de421.bsp")


def bright_bodies_azel(t_utc: datetime, lat: float | None = None, lon: float | None = None, h_m: float | None = None) -> list[dict[str, Any]]:
    lat = STATION["lat_deg"] if lat is None else lat
    lon = STATION["lon_deg"] if lon is None else lon
    h_m = STATION["h_m"] if h_m is None else h_m
    if t_utc.tzinfo is None:
        t_utc = t_utc.replace(tzinfo=timezone.utc)
    ts = LOADER.timescale()
    t = ts.from_datetime(t_utc.astimezone(timezone.utc))
    eph = _ephemeris()
    earth = eph["earth"]
    observer = earth + wgs84.latlon(lat, lon, elevation_m=h_m)
    out = []
    for name in BODIES:
        body = eph[name]
        app = observer.at(t).observe(body).apparent()
        alt, az, _ = app.altaz()
        out.append(
            {
                "name": name,
                "az_deg": round(float(az.degrees), 4),
                "el_deg": round(float(alt.degrees), 4),
                "above_horizon": bool(float(alt.degrees) > 0),
            }
        )
    return out


def check_h3(az_deg: float, el_deg: float, t_utc: datetime, sep_max: float = 0.2) -> dict[str, Any]:
    try:
        bodies = bright_bodies_azel(t_utc)
    except Exception as exc:
        return {
            "matched": False,
            "status": "PENDIENTE_DE_VERIFICACION",
            "error": str(exc),
            "bodies": [],
        }
    hits = []
    for b in bodies:
        if not b["above_horizon"]:
            continue
        sep = angular_sep_azel_deg(az_deg, el_deg, b["az_deg"], b["el_deg"])
        if sep < sep_max:
            hits.append({**b, "sep_deg": round(sep, 4)})
    hits.sort(key=lambda x: x["sep_deg"])
    return {"matched": bool(hits), "sep_max_deg": sep_max, "hits": hits, "bodies_checked": len(bodies)}
