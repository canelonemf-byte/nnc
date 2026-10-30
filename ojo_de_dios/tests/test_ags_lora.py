from ojo_de_dios.ags_lora import ags_core_supervisor_message, pack_lora_uplink


def test_lora_pack_len():
    det = {"id": "x", "az_deg": 12.34, "el_deg": 56.78, "evidencia": "E2", "excluido_por": "h1", "modo": "simulacion", "resultado": "aeronave_identificada"}
    ecef = {"x_m": 4.7e6, "y_m": 1.7e5, "z_m": 4.2e6}
    up = pack_lora_uplink(det, ecef)
    assert up["max_payload_bytes"] == 51
    assert up["packed_len"] <= 51
    assert up["status"] == "PENDIENTE_DE_VERIFICACION"
    assert up["hardware_lora"] is False


def test_ags_envelope():
    det = {"id": "x", "evidencia": "E1", "excluido_por": "", "resultado": "no_identificado_insuficiente", "modo": "simulacion", "riesgos": []}
    msg = ags_core_supervisor_message(det, {})
    assert msg["ags_core"]["untested"] is True
    assert msg["ags_core"]["schema"] == "ags_core_supervisor_v1"
