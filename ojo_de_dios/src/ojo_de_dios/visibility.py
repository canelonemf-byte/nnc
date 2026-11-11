"""
Optical visibility of satellite passes (not just geometry).

A sample at time t is *potencialmente_visible* iff:
  1. el_sat(t) >= min_el_deg (default 10 deg)
  2. satellite is sunlit: skyfield ICRF.is_sunlit(ephemeris) (Earth cylindrical+penumbra-free shadow test)
  3. observer is in darkness: sun altitude at observer <= sun_alt_max_deg (default -6 deg, civil twilight end)
Weather is NOT included in the geometric/optical class; it is reported separately
as an uncertainty (cloud cover from forecast is not observation of sky).
No brightness (magnitude) is computed -> no "brightest/best" claims.
"""
from __future__ import annotations

import math
from datetime import timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from skyfield.api import wgs84

from .astro import LOADER, _ephemeris

MADRID = ZoneInfo("Europe/Madrid")
CLASS_GEOM = "solo_geometrico"
CLASS_OPT = "potencialmente_visible_optico"


def _iso_pair(t) -> tuple[str, str]:
    dt = t.utc_datetime().replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z"), dt.astimezone(MADRID).isoformat(timespec="seconds")


def classify_passes(
    sat,
    lat: float,
    lon: float,
    h_m: float,
    hours: float = 36.0,
    min_el_deg: float = 10.0,
    sun_alt_max_deg: float = -6.0,
    step_s: int = 10,
    t_start=None,
    cloud_cover_pct: float | None = None,
) -> list[dict[str, Any]]:
    if not (math.isfinite(min_el_deg) and math.isfinite(sun_alt_max_deg)) or step_s <= 0:
        raise ValueError("parametros no finitos")
    ts = LOADER.timescale()
    eph = _ephemeris()
    earth, sun = eph["earth"], eph["sun"]
    topo = wgs84.latlon(lat, lon, elevation_m=h_m)
    observer = earth + topo
    t0 = t_start if t_start is not None else ts.now()
    t1 = ts.utc(t0.utc_datetime() + timedelta(hours=hours))
    times, events = sat.find_events(topo, t0, t1, altitude_degrees=min_el_deg)
    passes: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for ti, ei in zip(times, events):
        ei = int(ei)
        if ei == 0:
            cur = {"rise": ti}
        elif ei == 1 and cur is not None:
            cur["culm"] = ti
        elif ei == 2 and cur is not None:
            cur["set"] = ti
            passes.append(cur)
            cur = None
    out = []
    for p in passes:
        if "culm" not in p:
            continue
        dur = (p["set"].tt - p["rise"].tt) * 86400.0
        n = max(2, int(dur // step_s) + 1)
        tt = ts.tt_jd([p["rise"].tt + (p["set"].tt - p["rise"].tt) * k / (n - 1) for k in range(n)])
        alt, az, rng = (sat - topo).at(tt).altaz()
        sunlit = sat.at(tt).is_sunlit(eph)
        sun_alt = observer.at(tt).observe(sun).apparent().altaz()[0].degrees
        vis = (alt.degrees >= min_el_deg - 1e-6) & sunlit & (sun_alt <= sun_alt_max_deg)
        idx = [i for i in range(n) if bool(vis[i])]
        r_utc, r_mad = _iso_pair(p["rise"])
        c_utc, c_mad = _iso_pair(p["culm"])
        s_utc, s_mad = _iso_pair(p["set"])
        calt, caz, _ = (sat - topo).at(p["culm"]).altaz()
        row: dict[str, Any] = {
            "rise_utc": r_utc, "rise_madrid": r_mad,
            "culm_utc": c_utc, "culm_madrid": c_mad,
            "set_utc": s_utc, "set_madrid": s_mad,
            "culm_az_deg": round(float(caz.degrees), 2), "culm_el_deg": round(float(calt.degrees), 2),
            "rise_az_deg": round(float(az.degrees[0]), 2), "set_az_deg": round(float(az.degrees[-1]), 2),
            "samples": n, "step_s": step_s,
            "sunlit_fraction": round(float(sunlit.mean()), 3),
            "sun_alt_deg_min": round(float(sun_alt.min()), 2), "sun_alt_deg_max": round(float(sun_alt.max()), 2),
            "visible_samples": len(idx),
        }
        if idx:
            a, b = idx[0], idx[-1]
            va, vb = _iso_pair(tt[a]), _iso_pair(tt[b])
            imax = max(idx, key=lambda i: alt.degrees[i])
            row.update({
                "clase": CLASS_OPT,
                "visible_start_utc": va[0], "visible_start_madrid": va[1],
                "visible_end_utc": vb[0], "visible_end_madrid": vb[1],
                "visible_start_az_deg": round(float(az.degrees[a]), 2), "visible_start_el_deg": round(float(alt.degrees[a]), 2),
                "visible_end_az_deg": round(float(az.degrees[b]), 2), "visible_end_el_deg": round(float(alt.degrees[b]), 2),
                "visible_max_el_deg": round(float(alt.degrees[imax]), 2),
                "visible_duration_s": int(round((tt[b].tt - tt[a].tt) * 86400.0)),
            })
            if b < n - 1 and not bool(sunlit[b + 1]):
                row["nota_fin"] = "entra_en_sombra_terrestre"
        else:
            reasons = []
            if not bool(sunlit.any()):
                reasons.append("satelite_en_sombra_terrestre")
            if float(sun_alt.min()) > sun_alt_max_deg:
                reasons.append("cielo_no_oscuro_sol_sobre_umbral")
            if not reasons:
                reasons.append("sin_muestra_simultanea_iluminado_y_oscuro")
            row.update({"clase": CLASS_GEOM, "motivos": reasons})
        if row["clase"] == CLASS_OPT:
            if cloud_cover_pct is None:
                row["meteo"] = "incertidumbre_meteo_sin_dato"
            else:
                row["meteo"] = "incertidumbre_meteo_nubosidad_%d_pct_pronostico" % round(cloud_cover_pct)
        else:
            row["meteo"] = ""
        row["brillo"] = "no_calculado_sin_magnitud"
        row["umbrales"] = {"min_el_deg": min_el_deg, "sun_alt_max_deg": sun_alt_max_deg}
        out.append(row)
    return out
