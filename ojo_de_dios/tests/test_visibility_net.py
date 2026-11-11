"""Visibility + numerics + network adversity (offline, deterministic)."""
import math

import httpx
import pytest
from skyfield.api import EarthSatellite

from ojo_de_dios import meteo
from ojo_de_dios.astro import LOADER
from ojo_de_dios.math_geo import ecef_to_enu_azel
from ojo_de_dios.visibility import CLASS_GEOM, CLASS_OPT, classify_passes

from pathlib import Path

# Real Celestrak ISS TLE fetched 2026-11-05 (epoch 2026-11-04T21:15Z), frozen for reproducibility.
_L = [x for x in (Path(__file__).parent / "fixtures" / "iss_tle_epoch_20261104.txt").read_text().splitlines() if x.strip()]


def _sat():
    return EarthSatellite(_L[1], _L[2], _L[0].strip(), LOADER.timescale())


def test_regression_nov5_reported_passes_were_geometric_only():
    """The 21:42 and 23:19 (Europe/Madrid) culminations reported on 2026-11-05 are in Earth shadow."""
    ts = LOADER.timescale()
    ps = classify_passes(_sat(), 41.3275, 2.095, 59.0, hours=5, t_start=ts.utc(2026, 11, 5, 19))
    culms = {p["culm_madrid"][11:16]: p for p in ps}
    for hhmm in ("21:42", "23:19"):
        assert hhmm in culms and culms[hhmm]["clase"] == CLASS_GEOM and culms[hhmm]["sunlit_fraction"] == 0.0


def test_pass_classes_and_dark_sunlit_samples():
    ts = LOADER.timescale()
    ps = classify_passes(_sat(), 41.3275, 2.095, 59.0, hours=24 * 8, t_start=ts.utc(2026, 11, 5, 12))
    assert ps
    assert any(p["clase"] == CLASS_OPT for p in ps), "8 dias deberian incluir pases crepusculares iluminados"
    for p in ps:
        assert p["clase"] in (CLASS_GEOM, CLASS_OPT)
        assert p["brillo"] == "no_calculado_sin_magnitud"
        if p["clase"] == CLASS_OPT:
            assert p["visible_samples"] > 0 and p["visible_max_el_deg"] >= 10 and p["meteo"].startswith("incertidumbre_meteo")
        else:
            assert p["motivos"]


def test_deep_night_pass_is_geometric_only():
    ts = LOADER.timescale()
    # sun at ~-60deg near 01:00 local: ISS normally in Earth shadow at this latitude in November
    ps = classify_passes(_sat(), 41.3275, 2.095, 59.0, hours=6, t_start=ts.utc(2026, 11, 5, 23))
    deep = [p for p in ps if p["sun_alt_deg_max"] < -40]
    assert deep and all(p["clase"] == CLASS_GEOM for p in deep)


def test_daytime_threshold_blocks_visibility():
    ts = LOADER.timescale()
    ps = classify_passes(_sat(), 41.3275, 2.095, 59.0, hours=24, t_start=ts.utc(2026, 11, 6, 0), sun_alt_max_deg=-90)
    assert all(p["clase"] == CLASS_GEOM for p in ps)


def test_enu_zenith_and_horizon():
    z = ecef_to_enu_azel(41.0, 2.0, 0.0, 41.0, 2.0, 10000.0)
    assert abs(z["el_deg"] - 90) < 1e-6
    far = ecef_to_enu_azel(41.0, 2.0, 0.0, 41.0, 4.0, 0.0)  # ~168 km away at same height -> below horizon (curvature)
    assert far["el_deg"] < 0 and 80 < far["az_deg"] < 100


def test_retry_after_clamped_and_http_date():
    r = httpx.Response(429, headers={"Retry-After": "99999"})
    assert meteo._parse_retry_after(r) == meteo.MAX_RETRY_WAIT_S
    assert meteo._parse_retry_after(httpx.Response(429, headers={"Retry-After": "nan"})) is None
    assert meteo._parse_retry_after(httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})) == 0.0


def test_open_meteo_429_bounded_wait(monkeypatch):
    slept = []
    monkeypatch.setattr(meteo.time, "sleep", lambda s: slept.append(s))
    tr = httpx.MockTransport(lambda req: httpx.Response(429, headers={"Retry-After": "3600"}))
    with httpx.Client(transport=tr) as c:
        out = meteo._fetch_open_meteo(c, 41.3, 2.1)
    assert out["ok"] is False and sum(slept) <= meteo.MAX_TOTAL_WAIT_S


def test_network_error_falls_to_stale_cache(monkeypatch, tmp_path):
    cache = tmp_path / "meteo.json"
    cache.write_text('{"ok": true, "fuente": "open_meteo", "_cached_at": 0, "cloud_cover_pct": 10, "fetched_at_madrid": "X"}')
    monkeypatch.setattr(meteo, "CACHE_FILE", cache)

    def boom(req):
        raise httpx.ConnectError("down")
    real = httpx.Client
    monkeypatch.setattr(meteo.httpx, "Client", lambda **k: real(transport=httpx.MockTransport(boom)))
    monkeypatch.setattr(meteo.time, "sleep", lambda s: None)
    out = meteo.get_meteo()
    assert out["stale"] is True and out["original_fetched_at_madrid"] == "X" and out["cache_age_s"] > 0
    assert len(out["errores_fuentes"]) == 2
