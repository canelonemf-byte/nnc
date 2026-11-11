"""Tests offline de la vista Ojo de Dios (beta NNC).
Autoría: Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia IA."""
import json
import math
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ojo_vista as ov  # noqa: E402
from ojo_de_dios import hypotheses as hy  # noqa: E402


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """Cadena real H0-H7 con catálogo determinista: ISS fija az=100 el=30; ADS-B vía snapshot inyectado."""
    snap = {"aircraft": []}

    def sat(t, norad=25544, **k):
        return {"az_deg": 100.0, "el_deg": 30.0, "range_km": 800.0, "tle_fuente": "test", "sunlit": True}

    def adsb_x(**k):
        m = [dict(a, sep_deg=0.0) for a in snap["aircraft"]
             if a.get("el_deg") is not None and abs(a["az_deg"] - k["az_deg"]) < 1e-6 and abs(a["el_deg"] - k["el_deg"]) < 1e-6]
        return {"ok": True, "fuente": "test", "matches": m}

    monkeypatch.setattr(hy, "satellite_azel_at", sat)
    monkeypatch.setattr(hy, "check_h3", lambda *a, **k: {"matched": False, "hits": []})
    monkeypatch.setattr(hy, "adsb_crosscheck", adsb_x)
    monkeypatch.setattr(ov, "HIST_FILE", tmp_path / "h.jsonl")
    monkeypatch.setattr(ov, "DET_FILE", tmp_path / "det.jsonl")
    return snap


def _ac(hex_, lat, lon, az, el, gs=250.0, track=90.0, alt=20000.0, dist=10.0):
    return {"hex": hex_, "flight": hex_.upper(), "lat": lat, "lon": lon, "az_deg": az, "el_deg": el, "alt_ft": alt,
            "dist_km": dist, "gs_kt": gs, "track_deg": track, "on_ground": False, "slant_km": 12.0}


def _fuentes(snap, cached_at, iss_obs=None):
    return {
        "adsb": lambda: {"ok": True, "fuente": "test", "http_status": 200, "aircraft": snap["aircraft"], "_cached_at": cached_at},
        "tle": lambda: {"ok": True, "tle_fuente": "test", "tle_age_h": 12.0, "now": {"az_deg": 100.0, "el_deg": 30.0, "range_km": 800.0}, "pases": []},
        "meteo": lambda: {"ok": True, "fuente": "test", "http_status": 200, "cloud_cover_pct": 50},
        "iss_obs": lambda: (200, iss_obs) if iss_obs else (503, None),
        "iss_sgp4": lambda t: {"lat": 10.0, "lon": 20.0, "h_m": 420000.0},
        "evaluar": lambda det: hy.evaluate_detection(det, modo="experimento"),
    }


# ---- ω·R sin R
def test_omega_r_sin_R_no_calcula_v():
    r = ov.omega_r(0.01, None)
    assert r["R_m"] == "" and r["v_tan_m_s"] == "" and r["omega_rad_s"] == 0.01
    assert ov.omega_r(0.01, "")["v_tan_m_s"] == ""
    assert ov.omega_r(0.01, 0)["v_tan_m_s"] == ""
    assert ov.omega_r(0.01, float("nan"))["v_tan_m_s"] == ""


def test_omega_r_con_R_medida():
    r = ov.omega_r(0.01, 1000.0)
    assert math.isclose(r["v_tan_m_s"], 10.0)


# ---- desviación medible
def test_desviacion_trayectoria_recta_no_avisa():
    p = {"lat": 41.0, "lon": 2.0, "gs_kt": 400.0, "track_deg": 90.0}
    lat2, lon2 = ov.destino(41.0, 2.0, 90.0, 400 * 0.514444 * 30 / 1000.0)
    c = {"lat": lat2, "lon": lon2, "gs_kt": 400.0, "track_deg": 90.0}
    d = ov.desviacion_aeronave(p, c, 30.0)
    assert d["desviacion_medible"] is False and d["residuo_km"] < 0.01


def test_desviacion_salto_grande_avisa():
    p = {"lat": 41.0, "lon": 2.0, "gs_kt": 400.0, "track_deg": 90.0}
    c = {"lat": 41.2, "lon": 2.0, "gs_kt": 400.0, "track_deg": 90.0}  # ~22 km fuera de la estima
    d = ov.desviacion_aeronave(p, c, 30.0)
    assert d["desviacion_medible"] is True and d["n_sigma"] > 3


def test_desviacion_sin_dos_epocas_es_indeterminado():
    p = {"lat": 41.0, "lon": 2.0, "gs_kt": None, "track_deg": 90.0}
    assert ov.desviacion_aeronave(p, p, 30.0)["desviacion_medible"] == "indeterminado"
    q = {"lat": 41.0, "lon": 2.0, "gs_kt": 300.0, "track_deg": 90.0}
    assert ov.desviacion_aeronave(q, q, 1.0)["desviacion_medible"] == "indeterminado"


def test_desviacion_iss():
    a = {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0}
    assert ov.desviacion_iss(a, {"x_m": 1000.0, "y_m": 0.0, "z_m": 0.0}, 0.5)["desviacion_medible"] is False
    assert ov.desviacion_iss(a, {"x_m": 50000.0, "y_m": 0.0, "z_m": 0.0}, 0.5)["desviacion_medible"] is True
    assert ov.desviacion_iss(a, a, None)["desviacion_medible"] == "indeterminado"


# ---- silencio ADS-B
def test_silencio_adsb_es_indeterminado_sin_aviso():
    s = ov.silencio_adsb({"aaa", "bbb"}, {"bbb"})
    assert s == [{"hex": "aaa", "estado": "indeterminado", "motivo": "silencio_adsb_no_es_anomalia", "aviso": False}]


def test_vista_silencio_no_genera_aviso_y_explica_balizas(offline):
    st = ov.Estado()
    a1 = _ac("aaa", 41.3, 2.1, 90.0, 20.0)
    b1 = _ac("bbb", 41.4, 2.2, 45.0, 15.0)
    offline["aircraft"] = [a1, b1]
    t0 = time.time()
    v1 = ov.construir_vista(fuentes=_fuentes(offline, t0), estado=st, guardar=False)
    assert all(o["estado"] == "EXPLICADO" for o in v1["objetos"])
    ac = [o for o in v1["objetos"] if o["tipo"] == "aeronave_adsb"]
    assert {o["cadena"]["excluido_por"] for o in ac} == {"h1"}
    # segundo snapshot: 'bbb' desaparece (silencio), 'aaa' sigue en línea recta
    lat2, lon2 = ov.destino(41.3, 2.1, 90.0, 250 * 0.514444 * 30 / 1000.0)
    a2 = _ac("aaa", lat2, lon2, 90.5, 20.0)
    offline["aircraft"] = [a2]
    v2 = ov.construir_vista(fuentes=_fuentes(offline, t0 + 30), estado=st, guardar=False)
    assert [s["hex"] for s in v2["silencio_adsb"]] == ["bbb"]
    assert v2["silencio_adsb"][0]["estado"] == "indeterminado"
    assert v2["avisos"] == []
    o = [x for x in v2["objetos"] if x.get("hex") == "aaa"][0]
    assert o["desviacion"]["desviacion_medible"] is False
    assert o["cinematica"]["R_m"] == "" and o["cinematica"]["v_tan_m_s"] == "" and o["cinematica"]["omega_rad_s"] > 0


def test_vista_desviacion_genera_aviso_pero_sigue_explicado(offline):
    st = ov.Estado()
    offline["aircraft"] = [_ac("aaa", 41.3, 2.1, 90.0, 20.0)]
    t0 = time.time()
    ov.construir_vista(fuentes=_fuentes(offline, t0), estado=st, guardar=False)
    offline["aircraft"] = [_ac("aaa", 41.6, 2.1, 10.0, 20.0)]  # ~33 km fuera de la estima
    v = ov.construir_vista(fuentes=_fuentes(offline, t0 + 30), estado=st, guardar=False)
    assert len(v["avisos"]) == 1 and v["avisos"][0]["estado"] == "EXPLICADO"
    assert "no es FANI" in v["avisos"][0]["nota"]


# ---- nunca FANI, evidencia, detecciones
def test_nunca_fani_y_tope_E2_catalogo(offline):
    offline["aircraft"] = [_ac("aaa", 41.3, 2.1, 90.0, 20.0)]
    v = ov.construir_vista(fuentes=_fuentes(offline, time.time()), estado=ov.Estado(), guardar=False)
    assert v["fani_declarado"] is False
    assert v["evidencia_max_mostrada"] in ("E0", "E1", "E2")
    assert all(o["estado"] in ov.ESTADOS for o in v["objetos"])
    assert "fani_confirmado" not in json.dumps(v).lower()
    assert v["detecciones_opticas"] == [] and "sin detecciones ópticas reales" in v["detecciones_opticas_nota"]


def test_deteccion_optica_sin_explicar_es_pendiente_no_fani(offline, tmp_path):
    ov.DET_FILE.write_text(json.dumps({"id": "cam1", "az_deg": 300.0, "el_deg": 60.0, "origen": "observacion_optica",
                                       "t": "2026-01-01T00:00:00Z"}) + "\n")
    v = ov.construir_vista(fuentes=_fuentes(offline, time.time()), estado=ov.Estado(), guardar=False)
    d = v["detecciones_opticas"][0]
    assert d["estado"] == "no_explicado_pendiente"
    assert d["cadena"]["evidencia"] == "E1"  # óptica sin sync verificada
    assert d["cadena"]["anomaly_claim"] is False


def test_estado_desde_resultado_nunca_fani():
    for r in ({"excluido_por": "h1"}, {"excluido_por": ""}, {}, {"resultado": "no_identificado_hipotesis_convencionales_descartadas_con_dato"}):
        assert ov.estado_desde_resultado(r) in ("EXPLICADO", "no_explicado_pendiente")
    with pytest.raises(AssertionError):
        ov.assert_sin_fani({"estado": "FANI"})


def test_cap_evidencia():
    assert ov.cap_evidencia("sintetica_desde_catalogo", "E5") == "E2"
    assert ov.cap_evidencia("simulacion", "E3") == "E2"
    assert ov.cap_evidencia("observacion_optica", "E3") == "E3"
    assert ov.cap_evidencia("", "E3") == "E0"


# ---- filtros estrictos
def test_filtros_estrictos():
    with pytest.raises(ValueError):
        ov.parse_filtros({"radio_km": "1000"})
    with pytest.raises(ValueError):
        ov.parse_filtros({"radio_km": "nan"})
    with pytest.raises(ValueError):
        ov.parse_filtros({"zzz": "1"})
    with pytest.raises(ValueError):
        ov.parse_filtros({"alt_min_ft": "5000", "alt_max_ft": "1000"})
    f = ov.parse_filtros({"radio_km": ["20"], "el_min_deg": "5"})
    acs = [_ac("a", 0, 0, 0, 10.0, dist=10), _ac("b", 0, 0, 0, 2.0, dist=10), _ac("c", 0, 0, 0, 10.0, dist=50),
           dict(_ac("d", 0, 0, 0, 10.0), alt_ft=None), dict(_ac("e", 0, 0, 0, 10.0), on_ground=True)]
    ok, fuera = ov.aplicar_filtros(acs, f)
    assert [a["hex"] for a in ok] == ["a"]
    assert {x["hex"]: x["motivo"] for x in fuera} == {"b": "bajo_elevacion_minima", "c": "fuera_de_radio",
                                                       "d": "altitud_desconocida", "e": "en_tierra"}


def test_dato_antiguo_se_descarta(offline):
    offline["aircraft"] = [_ac("aaa", 41.3, 2.1, 90.0, 20.0)]
    v = ov.construir_vista(filtros=ov.parse_filtros({"edad_max_s": "10"}), fuentes=_fuentes(offline, time.time() - 300),
                           estado=ov.Estado(), guardar=False)
    assert [o for o in v["objetos"] if o["tipo"] == "aeronave_adsb"] == []
    assert v["fuentes"]["adsb"]["descartado"] == "dato_mas_antiguo_que_edad_max_s"


def test_adsb_caido_no_es_anomalia(offline):
    F = _fuentes(offline, time.time())
    F["adsb"] = lambda: {"ok": False, "fuente": "airplanes_live", "http_status": 403, "aircraft": []}
    v = ov.construir_vista(fuentes=F, estado=ov.Estado(), guardar=False)
    assert v["silencio_adsb_global"]["estado"] == "indeterminado" and v["avisos"] == []


def test_historial_jsonl(offline):
    st = ov.Estado()
    ov.construir_vista(fuentes=_fuentes(offline, time.time()), estado=st, guardar=True)
    h = ov.leer_historial(5)
    assert len(h) == 1 and h[0]["fani_declarado"] is False and "t_madrid" in h[0]
