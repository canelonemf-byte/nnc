import pytest

from ojo_de_dios import hypotheses as hy


@pytest.fixture
def offline(monkeypatch):
    """Deterministic offline catalog: ISS fixed at az=100 el=30; no astro; no ADS-B match."""
    calls = {"adsb": 0}

    def sat(t, norad=25544, **k):
        return {"az_deg": 100.0, "el_deg": 30.0, "range_km": 800.0, "tle_fuente": "test"}

    def adsb(**k):
        calls["adsb"] += 1
        return {"ok": True, "fuente": "test", "matches": []}

    monkeypatch.setattr(hy, "satellite_azel_at", sat)
    monkeypatch.setattr(hy, "check_h3", lambda *a, **k: {"matched": False, "hits": []})
    monkeypatch.setattr(hy, "adsb_crosscheck", adsb)
    return calls
