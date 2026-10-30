"""
AGs-Core + LoRa uplink schema.

No LoRa hardware is present. This module only defines:
  - compact binary/JSON uplink idea (payload <= 51 bytes for LoRaWAN SF12-ish)
  - AGs-Core Supervisor message envelope

All marked UNTESTED / PENDIENTE_DE_VERIFICACION.
"""
from __future__ import annotations

import struct
from typing import Any


# Compact binary layout (51 bytes max idea):
# 0-1   magic 'OD' (0x4F44)
# 2     version u8
# 3     flags u8 (bit0=experimento, bit1=dual_cam, bit2=gnss)
# 4-7   unix_ts u32 BE
# 8-9   az_cdeg i16 (az*100)
# 10-11 el_cdeg i16 (el*100)
# 12    evidence u8 (0-6)
# 13    excluded_by u8 (0=none,1=h0..10=h_mat)
# 14-15 duration_cs u16 (centiseconds)
# 16-19 ecef_x_km_q i32 (X/1000 * 1000? store X metres / 10 as i32 → ~cm*10)
# Actually store ECEF as int32 metres (sufficient ±2e9 m)
# 16-19 ecef_x_m i32
# 20-23 ecef_y_m i32
# 24-27 ecef_z_m i32
# 28-31 det_hash_prefix u32 (first 4 bytes of sha256)
# 32-35 reserved
# total 36 bytes core; remaining for callsign ASCII up to 8 chars + pad → <=51

H_CODE = {
    "": 0,
    "h0": 1,
    "h1": 2,
    "h2": 3,
    "h3": 4,
    "h4": 5,
    "h5": 6,
    "h6": 7,
    "h7": 8,
    "h_kin": 9,
    "h_mat": 10,
}


def pack_lora_uplink(det_result: dict[str, Any], ecef: dict[str, float] | None = None) -> dict[str, Any]:
    """Build schema + optional packed bytes. UNTESTED on radio."""
    ecef = ecef or {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0}
    az = float(det_result.get("az_deg") or 0.0)
    el = float(det_result.get("el_deg") or 0.0)
    evid = int(str(det_result.get("evidencia") or "E0")[1:])
    excl = H_CODE.get(det_result.get("excluido_por") or "", 0)
    # timestamp from evaluado or 0
    ts = 0
    flags = 0
    if det_result.get("modo") == "experimento":
        flags |= 0x01
    schema = {
        "protocol": "ojo_de_dios_lora_v1",
        "status": "PENDIENTE_DE_VERIFICACION",
        "hardware_lora": False,
        "max_payload_bytes": 51,
        "fields": {
            "magic": "OD",
            "version": 1,
            "flags": flags,
            "unix_ts": ts,
            "az_cdeg": int(round(az * 100)),
            "el_cdeg": int(round(el * 100)),
            "evidence": evid,
            "excluded_by_code": excl,
            "ecef_x_m": int(round(ecef.get("x_m", 0))),
            "ecef_y_m": int(round(ecef.get("y_m", 0))),
            "ecef_z_m": int(round(ecef.get("z_m", 0))),
            "det_id": det_result.get("id") or "",
            "resultado": det_result.get("resultado") or "",
        },
        "note": "Schema only; no LoRa radio present. UNTESTED.",
    }
    try:
        packed = struct.pack(
            ">2sBBIhhBBIII",
            b"OD",
            1,
            flags,
            ts,
            int(round(az * 100)),
            int(round(el * 100)),
            evid,
            excl,
            int(round(ecef.get("x_m", 0))),
            int(round(ecef.get("y_m", 0))),
            int(round(ecef.get("z_m", 0))),
        )
        # >2sBBIhhBBIII = 2+1+1+4+2+2+1+1+4+4+4 = 26 bytes
        schema["packed_hex"] = packed.hex()
        schema["packed_len"] = len(packed)
    except Exception as exc:
        schema["packed_hex"] = ""
        schema["pack_error"] = str(exc)
    return schema


def ags_core_supervisor_message(det_result: dict[str, Any], lora: dict[str, Any] | None = None) -> dict[str, Any]:
    """AGs-Core Supervisor envelope (JSON). UNTESTED integration."""
    return {
        "ags_core": {
            "schema": "ags_core_supervisor_v1",
            "status": "PENDIENTE_DE_VERIFICACION",
            "untested": True,
            "proyecto": "ojo_de_dios_nnc",
            "version": "2.0",
            "supervisor": {
                "action": "ingest_detection",
                "priority": "normal" if det_result.get("excluido_por") else "review",
                "evidence": det_result.get("evidencia") or "E0",
                "resultado": det_result.get("resultado") or "",
                "excluido_por": det_result.get("excluido_por") or "",
                "modo": det_result.get("modo") or "",
                "detection_id": det_result.get("id") or "",
                "riesgos": det_result.get("riesgos") or [],
            },
            "lora_uplink": lora or {},
            "note": "AGs-Core+LoRa defined for future wire-up; no hardware / no supervisor endpoint live.",
        }
    }
