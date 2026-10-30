from ojo_de_dios.hypotheses import evaluate_detection


def test_h0_artefact():
    r = evaluate_detection(
        {"id": "t0", "t": "2026-10-30T18:00:00+00:00", "az_deg": 10, "el_deg": 10, "single_frame": True, "frames": 1},
        modo="simulacion",
    )
    assert r["excluido_por"] == "h0"
    assert r["resultado"] == "artefacto_sensor"
    assert r["hipotesis"]["h0"] is True


def test_h1_forced_aircraft():
    ac = {
        "flight": "TEST123",
        "hex": "abc123",
        "az_deg": 100.0,
        "el_deg": 20.0,
        "dist_km": 5.0,
        "alt_ft": 10000,
        "sep_deg": 0.1,
        "fuente": "test",
    }
    r = evaluate_detection(
        {
            "id": "t1",
            "t": "2026-10-30T18:00:00+00:00",
            "az_deg": 100.0,
            "el_deg": 20.0,
            "frames": 20,
            "force_h1": True,
            "adsb_aircraft": ac,
        },
        modo="simulacion",
    )
    assert r["excluido_por"] == "h1"
    assert r["resultado"] == "aeronave_identificada"
    assert r["evidencia"] == "E2"


def test_h2_forced_sat():
    r = evaluate_detection(
        {
            "id": "t2",
            "t": "2026-10-30T22:14:44+00:00",
            "az_deg": 132.6,
            "el_deg": 19.68,
            "frames": 100,
            "norad_hint": 25544,
            "force_h2": True,
        },
        modo="simulacion",
    )
    assert r["excluido_por"] == "h2"
    assert r["resultado"] == "satelite_identificado"


def test_h6_meteor():
    r = evaluate_detection(
        {
            "id": "t6",
            "t": "2026-10-30T18:00:00+00:00",
            "az_deg": 200,
            "el_deg": 40,
            "duration_s": 1.5,
            "trajectory_linear": True,
            "frames": 10,
        },
        modo="simulacion",
    )
    assert r["excluido_por"] == "h6"
    assert r["resultado"] == "meteoro_o_reentrada"


def test_unidentified_no_anomaly_claim():
    r = evaluate_detection(
        {
            "id": "t_fani",
            "t": "2026-10-30T18:00:00+00:00",
            "az_deg": 42,
            "el_deg": 55,
            "duration_s": 25,
            "frames": 30,
            "trajectory_linear": False,
        },
        modo="simulacion",
    )
    assert r["excluido_por"] == ""
    assert r["resultado"] == "no_identificado_insuficiente"
    assert r["detalles"]["anomaly_claim"] is False
    assert r["evidencia"] in ("E1", "E2")
    assert "h_kin_no_medible" in r["riesgos"]


def test_evidence_cap_without_dual():
    r = evaluate_detection(
        {
            "id": "tcap",
            "t": "2026-10-30T18:00:00+00:00",
            "az_deg": 1,
            "el_deg": 1,
            "force_h1": True,
            "adsb_aircraft": {"flight": "X", "az_deg": 1, "el_deg": 1, "sep_deg": 0},
        },
        modo="experimento",
    )
    # even experimento aircraft → at most E3 without dual+gnss
    assert r["evidencia"] in ("E0", "E1", "E2", "E3")
