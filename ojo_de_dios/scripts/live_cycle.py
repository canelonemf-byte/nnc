#!/usr/bin/env python3
"""Live verification cycle: probe APIs, real aircraft, ISS pass, synthetic FANI."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ojo_de_dios import adsb as adsb_mod
from ojo_de_dios import meteo as meteo_mod
from ojo_de_dios import tle as tle_mod
from ojo_de_dios.ags_lora import ags_core_supervisor_message, pack_lora_uplink
from ojo_de_dios.config import HARDWARE, STATION, STATE
from ojo_de_dios.hypotheses import evaluate_detection
from ojo_de_dios.math_geo import equations_doc, sha256_canonical, wgs84_to_ecef

MADRID = ZoneInfo("Europe/Madrid")
OUT = ROOT / "data" / "live_cycle_result.json"


def probe_table() -> list[dict]:
    rows = []
    # Meteo Open-Meteo / MET Norway
    meteo = meteo_mod.get_meteo(force=True)
    rows.append(
        {
            "api": "meteo",
            "fuente": meteo.get("fuente"),
            "http_status": meteo.get("http_status"),
            "time_madrid": meteo.get("fetched_at_madrid"),
            "ok": meteo.get("ok"),
            "sample": {
                "cloud_cover_pct": meteo.get("cloud_cover_pct"),
                "wind_speed_10m": meteo.get("wind_speed_10m"),
                "wind_direction_10m_deg": meteo.get("wind_direction_10m_deg"),
                "visibility_m": meteo.get("visibility_m"),
            },
        }
    )
    # TLE
    tle = tle_mod.fetch_celestrak_tle(25544, force=True)
    rows.append(
        {
            "api": "tle_celestrak",
            "fuente": tle.get("fuente"),
            "http_status": tle.get("http_status") or tle.get("http_status_json"),
            "time_madrid": tle.get("fetched_at_madrid"),
            "ok": tle.get("ok"),
            "sample": {
                "norad": 25544,
                "object": (tle.get("gp") or {}).get("OBJECT_NAME"),
                "epoch": (tle.get("gp") or {}).get("EPOCH"),
            },
        }
    )
    # ADS-B
    adsb = adsb_mod.get_adsb(force=True)
    rows.append(
        {
            "api": "adsb",
            "fuente": adsb.get("fuente"),
            "http_status": adsb.get("http_status"),
            "time_madrid": adsb.get("fetched_at_madrid"),
            "ok": adsb.get("ok"),
            "sample": {
                "count": adsb.get("count"),
                "nearest_flight": ((adsb.get("aircraft") or [{}])[0].get("flight") if adsb.get("aircraft") else ""),
            },
        }
    )
    # airplanes.live status (explicit probe for table)
    import httpx
    from ojo_de_dios.config import USER_AGENT

    with httpx.Client(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
        r_al = client.get(
            f"https://api.airplanes.live/v2/point/{STATION['lat_deg']}/{STATION['lon_deg']}/50"
        )
        r_os = client.get(
            "https://opensky-network.org/api/states/all",
            params={"lamin": 41.0, "lamax": 41.6, "lomin": 1.7, "lomax": 2.5},
        )
        r_met = client.get(
            "https://api.met.no/weatherapi/locationforecast/2.0/compact",
            params={"lat": STATION["lat_deg"], "lon": STATION["lon_deg"]},
            headers={"User-Agent": USER_AGENT},
        )
    rows.append(
        {
            "api": "opensky",
            "fuente": "opensky",
            "http_status": r_os.status_code,
            "time_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
            "ok": r_os.status_code == 200,
            "sample": {"bytes": len(r_os.content)},
        }
    )
    rows.append(
        {
            "api": "airplanes_live",
            "fuente": "airplanes_live",
            "http_status": r_al.status_code,
            "time_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
            "ok": r_al.status_code == 200,
            "sample": {"error": r_al.text[:120] if r_al.status_code != 200 else ""},
        }
    )
    rows.append(
        {
            "api": "met_norway",
            "fuente": "met_norway",
            "http_status": r_met.status_code,
            "time_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
            "ok": r_met.status_code == 200,
            "sample": {},
        }
    )
    STATE.live_probes = {r["api"]: r for r in rows}
    return rows


def main() -> None:
    print("=== LIVE PROBES ===")
    table = probe_table()
    for r in table:
        print(f"{r['api']:16} HTTP {r['http_status']}  fuente={r['fuente']}  @ {r['time_madrid']}")

    print("\n=== ADS-B REAL AIRCRAFT ===")
    snap = adsb_mod.get_adsb(force=True)
    airborne = [a for a in (snap.get("aircraft") or []) if not a.get("on_ground") and a.get("el_deg") is not None and (a.get("alt_ft") or 0) > 0 and (a.get("el_deg") or -1) > 0]
    ezy = [a for a in (snap.get("aircraft") or []) if "EZY95FN" in (a.get("flight") or "").upper().replace(" ", "")]
    print(f"EZY95FN present: {bool(ezy)}")
    if not airborne:
        print("No airborne aircraft with computed el — PENDIENTE")
        chosen = {}
    else:
        chosen = airborne[0]
        print("Chosen (nearest airborne):", json.dumps(chosen, ensure_ascii=False))

    print("\n=== ISS PASS ===")
    iss = tle_mod.predict_pass(norad=25544, hours=24.0, min_el_deg=10.0)
    print("next_culmination:", json.dumps(iss.get("next_culmination") or {}, ensure_ascii=False))
    print("tle_epoch:", iss.get("tle_epoch"))

    # --- Case A: real aircraft ---
    if chosen:
        det_a = {
            "id": "det_live_aircraft",
            "t": datetime.now(timezone.utc).isoformat(),
            "az_deg": chosen["az_deg"],
            "el_deg": chosen["el_deg"],
            "frames": 40,
            "duration_s": 12.0,
            "single_camera": True,
            "force_h1": True,
            "adsb_aircraft": chosen,
            "callsign_hint": chosen.get("flight") or "",
        }
        modo_a = "experimento"
    else:
        det_a = {
            "id": "det_live_aircraft",
            "t": datetime.now(timezone.utc).isoformat(),
            "az_deg": 0.0,
            "el_deg": 0.0,
            "frames": 0,
            "note": "PENDIENTE_DE_VERIFICACION: no airborne target",
        }
        modo_a = "experimento"
    res_a = evaluate_detection(det_a, modo=modo_a)

    # --- Case B: real ISS at culmination time ---
    culm = iss.get("next_culmination") or {}
    if culm:
        det_b = {
            "id": "det_live_iss",
            "t": culm["t_utc"],
            "az_deg": culm["az_deg"],
            "el_deg": culm["el_deg"],
            "frames": 180,
            "duration_s": 300.0,
            "norad_hint": 25544,
            "force_h2": True,
            "single_camera": True,
        }
        res_b = evaluate_detection(det_b, modo="experimento")
    else:
        res_b = {"id": "det_live_iss", "resultado": "PENDIENTE_DE_VERIFICACION", "excluido_por": ""}

    # --- Case C: synthetic unidentified SIMULACION ---
    det_c = {
        "id": "det_sim_fani",
        "t": datetime.now(timezone.utc).isoformat(),
        "az_deg": 42.0,
        "el_deg": 55.0,
        "frames": 30,
        "duration_s": 25.0,
        "single_camera": True,
        "trajectory_linear": False,
    }
    res_c = evaluate_detection(det_c, modo="simulacion")

    ecef = wgs84_to_ecef(STATION["lat_deg"], STATION["lon_deg"], STATION["h_m"])
    for res in (res_a, res_b, res_c):
        if isinstance(res, dict) and "resultado" in res:
            lora = pack_lora_uplink(res, ecef)
            res["lora_uplink"] = lora
            res["ags_core"] = ags_core_supervisor_message(res, lora)["ags_core"]

    cycle = {
        "meta": {
            "proyecto": "ojo_de_dios_nnc",
            "version": "2.0",
            "generated_at_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
            "station": STATION,
            "hardware": HARDWARE,
            "equations": equations_doc(),
            "note": "Aircraft and ISS from live APIs; FANI case is SIMULACION only.",
        },
        "live_api_table": table,
        "real_aircraft": {
            "ezy95fn_present": bool(ezy),
            "ezy95fn_note": "EZY95FN not in current ADS-B snapshot; using nearest airborne instead."
            if not ezy
            else "EZY95FN present",
            "chosen": chosen,
            "fuente": snap.get("fuente"),
        },
        "iss_pass": {
            "norad": 25544,
            "tle_epoch": iss.get("tle_epoch"),
            "tle_fuente": iss.get("tle_fuente"),
            "next_culmination": culm,
            "events_count": len(iss.get("events") or []),
        },
        "ecef_station": {
            **ecef,
            "input_sha256": sha256_canonical(
                {"lat_deg": STATION["lat_deg"], "lon_deg": STATION["lon_deg"], "h_m": STATION["h_m"]}
            ),
            "coord_status": STATION["coord_status"],
        },
        "detecciones": [res_a, res_b, res_c],
    }
    OUT.write_text(json.dumps(cycle, ensure_ascii=False, indent=2))
    print("\n=== CYCLE SUMMARY ===")
    for d in cycle["detecciones"]:
        print(
            f"{d.get('id')}: excluido_por={d.get('excluido_por')!r} "
            f"resultado={d.get('resultado')} evidencia={d.get('evidencia')} modo={d.get('modo')}"
        )
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
