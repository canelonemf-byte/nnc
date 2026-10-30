from fastapi.testclient import TestClient

from ojo_de_dios.api import app

client = TestClient(app)


def test_status():
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["proyecto"] == "ojo_de_dios_nnc"
    assert body["estacion"]["coord_status"] == "PENDIENTE_DE_VERIFICACION"


def test_audit_ecef():
    r = client.post("/api/v1/audit/ecef", json={"lat_deg": 41.3275, "lon_deg": 2.0950, "h_m": 10.0, "id": "st"})
    assert r.status_code == 200
    body = r.json()
    assert "x_m" in body["ecef"]
    assert len(body["input_sha256"]) == 64


def test_hypotheses_h0():
    r = client.post(
        "/api/v1/hypotheses/check",
        json={"id": "a", "az_deg": 1, "el_deg": 1, "single_frame": True, "frames": 1, "modo": "simulacion"},
    )
    assert r.status_code == 200
    assert r.json()["excluido_por"] == "h0"
