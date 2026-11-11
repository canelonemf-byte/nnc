from ojo_de_dios import hypotheses as hy
from ojo_de_dios.hypotheses import evaluate_detection

T = "2026-11-05T20:00:00Z"


def test_catalog_capped_e2_even_with_tsync(offline, monkeypatch):
    monkeypatch.setitem(hy.HARDWARE, "ntp", True)
    r = evaluate_detection({"az_deg": 100, "el_deg": 30, "t": T, "origen": "sintetica_desde_catalogo", "t_sync": True})
    assert r["excluido_por"] == "h2" and r["evidencia"] == "E2" and r["modo"] == "validacion_pipeline"


def test_simulation_capped_e2(offline):
    assert evaluate_detection({"az_deg": 1, "el_deg": 1, "t": T}, modo="simulacion")["evidencia"] == "E2"


def test_optical_without_sync_is_e1(offline):
    r = evaluate_detection({"az_deg": 1, "el_deg": 1, "t": T, "origen": "observacion_optica"})
    assert r["evidencia"] == "E1" and r["t_sync"] is False


def test_tsync_flag_alone_is_not_sync(offline):
    r = evaluate_detection({"az_deg": 1, "el_deg": 1, "t": T, "origen": "observacion_optica", "t_sync": True})
    assert r["t_sync"] is False and r["evidencia"] == "E1"


def test_optical_with_sync_e3(offline, monkeypatch):
    monkeypatch.setitem(hy.HARDWARE, "ntp", True)
    r = evaluate_detection({"az_deg": 1, "el_deg": 1, "t": T, "origen": "observacion_optica", "t_sync": True})
    assert r["evidencia"] == "E3" and "no prueba" in r["evidencia_nota"]


def test_e4_requires_dual_coincident(offline, monkeypatch):
    for k in ("ntp", "gnss", "camaras_duales"):
        monkeypatch.setitem(hy.HARDWARE, k, True)
    base = {"az_deg": 1, "el_deg": 1, "t": T, "origen": "observacion_optica", "t_sync": True}
    assert evaluate_detection(base)["evidencia"] == "E3"
    assert evaluate_detection({**base, "camaras_coincidentes": 2})["evidencia"] == "E4"
    assert evaluate_detection({**base, "camaras_coincidentes": 2, "fuente_independiente": True})["evidencia"] == "E5"
