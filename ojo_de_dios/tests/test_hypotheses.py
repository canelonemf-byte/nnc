import math

import pytest

from ojo_de_dios import hypotheses as hy
from ojo_de_dios.hypotheses import IND, evaluate_detection

T = "2026-11-05T20:00:00Z"


def test_single_frame_is_not_proof_of_h0(offline):
    r = evaluate_detection({"az_deg": 10, "el_deg": 10, "t": T, "single_frame": True, "frames": 1}, modo="simulacion")
    assert r["hipotesis"]["h0"] == IND and r["excluido_por"] != "h0"


def test_confirmed_artefact_excludes_h0(offline):
    r = evaluate_detection({"az_deg": 10, "el_deg": 10, "t": T, "artefacto_sensor": True}, modo="simulacion")
    assert r["excluido_por"] == "h0"


def test_no_adsb_match_is_indeterminate_not_false(offline, monkeypatch):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    r = evaluate_detection({"az_deg": 200, "el_deg": 40, "t": now, "origen": "observacion_optica"})
    assert offline["adsb"] == 1
    assert r["hipotesis"]["h1"] == IND and r["hipotesis"]["h1"] is not False


def test_old_detection_not_crosschecked_with_live_snapshot(offline):
    r = evaluate_detection({"az_deg": 200, "el_deg": 40, "t": "2020-01-01T00:00:00Z", "origen": "observacion_optica"})
    assert offline["adsb"] == 0 and r["detalles"]["h1"]["motivo"].startswith("snapshot_adsb_no_contemporaneo")


def test_force_forbidden_for_observation(offline):
    with pytest.raises(ValueError):
        evaluate_detection({"az_deg": 1, "el_deg": 1, "origen": "observacion_optica", "force_h1": True,
                            "adsb_aircraft": {"flight": "X"}})


def test_forced_is_not_production(offline):
    r = evaluate_detection({"az_deg": 1, "el_deg": 1, "t": T, "force_h1": True, "adsb_aircraft": {"flight": "X"}})
    assert r["excluido_por"] == "h1" and r["conclusion_produccion"] is False and r["evidencia"] == "E2"


def test_h2_real_geometry_match_within_window(offline):
    r = evaluate_detection({"az_deg": 100.1, "el_deg": 30.1, "t": T, "origen": "sintetica_desde_catalogo"})
    assert r["excluido_por"] == "h2" and r["detalles"]["h2"]["sep_min_deg"] < 0.3


def test_h2_miss_is_indeterminate(offline):
    r = evaluate_detection({"az_deg": 300, "el_deg": 30, "t": T, "origen": "sintetica_desde_catalogo"})
    assert r["hipotesis"]["h2"] == IND


def test_h6_meteor(offline):
    r = evaluate_detection({"az_deg": 200, "el_deg": 40, "t": T, "duration_s": 1.5, "trajectory_linear": True}, modo="simulacion")
    assert r["excluido_por"] == "h6"


def test_unknowns_never_false_and_no_anomaly(offline):
    r = evaluate_detection({"az_deg": 42, "el_deg": 55, "t": T, "duration_s": 25}, modo="simulacion")
    assert r["resultado"] == "no_identificado_insuficiente" and r["anomaly_claim"] is False
    for h in ("h0", "h1", "h4", "h5", "h6", "h7", "h_kin", "h_mat"):
        assert r["hipotesis"][h] == IND


def test_h_kin_needs_distances_and_errors(offline, monkeypatch):
    monkeypatch.setitem(hy.HARDWARE, "camaras_duales", True)
    monkeypatch.setitem(hy.HARDWARE, "ntp", True)
    r = evaluate_detection({"az_deg": 42, "el_deg": 55, "t": T, "origen": "observacion_optica", "t_sync": True, "accel_g": 500})
    assert r["hipotesis"]["h_kin"] == IND and "distance_m" in r["detalles"]["h_kin"]["faltan"]


def test_h_kin_flag_never_excludes_or_claims(offline, monkeypatch):
    monkeypatch.setitem(hy.HARDWARE, "camaras_duales", True)
    monkeypatch.setitem(hy.HARDWARE, "ntp", True)
    r = evaluate_detection({"az_deg": 42, "el_deg": 55, "t": "2020-01-01T00:00:00Z", "origen": "observacion_optica", "t_sync": True,
                            "accel_g": 500, "accel_err_g": 10, "distance_m": 2000, "distance_err_m": 50})
    assert r["hipotesis"]["h_kin"] is True and r["excluido_por"] == "" and r["anomaly_claim"] is False
    assert "cinematica_fuera_de_envolvente_requiere_revision" in r["banderas"]


def test_h_kin_within_3sigma_not_flagged(offline, monkeypatch):
    monkeypatch.setitem(hy.HARDWARE, "camaras_duales", True)
    monkeypatch.setitem(hy.HARDWARE, "ntp", True)
    r = evaluate_detection({"az_deg": 42, "el_deg": 55, "t": "2020-01-01T00:00:00Z", "origen": "observacion_optica", "t_sync": True,
                            "accel_g": 60, "accel_err_g": 10, "distance_m": 2000, "distance_err_m": 50})
    assert r["hipotesis"]["h_kin"] is False


def test_h_mat_indeterminate_without_sensor(offline):
    r = evaluate_detection({"az_deg": 42, "el_deg": 55, "t": T, "spectral_anomaly": True}, modo="simulacion")
    assert r["hipotesis"]["h_mat"] == IND


@pytest.mark.parametrize("bad", [{"az_deg": math.nan, "el_deg": 1}, {"az_deg": 1, "el_deg": math.inf},
                                 {"az_deg": 1, "el_deg": 95}, {"az_deg": 1, "el_deg": 1, "t": "2026-11-05T20:00:00"},
                                 {"az_deg": 1, "el_deg": 1, "origen": "inventado"}, {"az_deg": 1, "el_deg": 1, "accel_g": math.nan}])
def test_invalid_inputs_rejected(offline, bad):
    with pytest.raises(ValueError):
        evaluate_detection(bad, modo="simulacion")
