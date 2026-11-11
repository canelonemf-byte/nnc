"""
Deterministic exclusion tree H0..H7 (+ H_kin, H_mat as flags).

Values are tri-state: True (explicada por esta hipotesis), False (descartada con dato),
"indeterminado" (sin dato suficiente). Unknown is NEVER False.
Fixed order; the first True excludes; all evaluated and logged.
H_kin and H_mat never exclude and never establish exotic origin.

Evidence (E0..E6) is driven by provenance (origen), not by HTTP success:
  simulacion / sintetica_desde_catalogo -> max E2 (validacion de pipeline / modelo)
  observacion_optica sin sync verificada -> E1
  observacion_optica + sync (config GNSS/NTP + t_sync) -> E3
  + camaras duales coincidentes + GNSS + NTP -> E4; + fuente independiente -> E5; + revision externa -> E6
Hardware flags come from config.HARDWARE (declarations, not proof of working hardware).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .adsb import crosscheck as adsb_crosscheck
from .astro import check_h3
from .config import HARDWARE, STATION, THRESHOLDS
from .math_geo import angular_sep_azel_deg
from .tle import satellite_azel_at

MADRID = ZoneInfo("Europe/Madrid")
H_ORDER = ["h0", "h1", "h2", "h3", "h4", "h5", "h6", "h7", "h_kin", "h_mat"]
EXCLUDING = ["h0", "h1", "h2", "h3", "h4", "h5", "h6", "h7"]
IND = "indeterminado"
ORIGENES = ("observacion_optica", "sintetica_desde_catalogo", "simulacion")
E_ORDER = ["E0", "E1", "E2", "E3", "E4", "E5", "E6"]
RESULT_BY_H = {
    "h0": "artefacto_sensor", "h1": "aeronave_identificada", "h2": "satelite_identificado",
    "h3": "astro_identificado", "h4": "meteo_o_globo", "h5": "objeto_cercano",
    "h6": "meteoro_o_reentrada", "h7": "fenomeno_optico",
}


def _parse_t(t: str | None) -> datetime:
    if not t:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("t debe incluir zona horaria (ISO8601 con Z u offset)")
    return dt.astimezone(timezone.utc)


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _resolve_origen(det: dict[str, Any], modo: str) -> str:
    o = det.get("origen") or ""
    if not o:
        if det.get("force_h1") or det.get("force_h2") or det.get("adsb_aircraft"):
            o = "sintetica_desde_catalogo"
        elif modo == "simulacion":
            o = "simulacion"
        else:
            o = "observacion_optica"
    if o not in ORIGENES:
        raise ValueError(f"origen invalido: {o}")
    if o == "observacion_optica" and (det.get("force_h1") or det.get("force_h2")):
        raise ValueError("force_h1/force_h2 prohibido en observacion_optica (no es evidencia)")
    return o


def _sync_verified(det: dict[str, Any]) -> bool:
    return bool(det.get("t_sync")) and bool(HARDWARE.get("gnss") or HARDWARE.get("ntp"))


def _evidence(origen: str, synced: bool, det: dict[str, Any]) -> tuple[str, str]:
    if origen == "simulacion":
        return "E2", "cap_E2: simulacion"
    if origen == "sintetica_desde_catalogo":
        return "E2", "cap_E2: validacion_de_pipeline_no_observacion"
    if not synced:
        return "E1", "E1: observacion_unica_sin_sincronizacion_verificada"
    e = "E3"
    dual = HARDWARE.get("camaras_duales") and HARDWARE.get("gnss") and HARDWARE.get("ntp") and int(det.get("camaras_coincidentes") or 0) >= 2
    if dual:
        e = "E4"
        if det.get("fuente_independiente"):
            e = "E5"
            if det.get("revision_externa"):
                e = "E6"
    return e, f"{e}: segun_config_hardware_declarada (no prueba de funcionamiento)"


def evaluate_detection(det: dict[str, Any], modo: str = "experimento") -> dict[str, Any]:
    for k in ("az_deg", "el_deg"):
        if not _finite(det.get(k)):
            raise ValueError(f"{k} no finito o ausente")
    az, el = float(det["az_deg"]) % 360.0, float(det["el_deg"])
    if not -90.0 <= el <= 90.0:
        raise ValueError("el_deg fuera de [-90,90]")
    for k in ("duration_s", "accel_g", "accel_err_g", "distance_m", "distance_err_m", "wind_drift_error_pct"):
        if det.get(k) is not None and not _finite(det[k]):
            raise ValueError(f"{k} no finito")
    t_utc = _parse_t(det.get("t"))
    origen = _resolve_origen(det, modo)
    if origen != "observacion_optica":
        modo = "simulacion" if origen == "simulacion" else "validacion_pipeline"
    synced = _sync_verified(det)
    log: dict[str, Any] = {}
    d: dict[str, Any] = {}

    # H0 artefacto: single frame / single camera is NOT proof of artefact.
    if det.get("artefacto_sensor"):
        log["h0"] = True
        d["h0"] = {"motivo": "artefacto_sensor_confirmado_por_entrada"}
    elif int(det.get("camaras_coincidentes") or 0) >= 2 and HARDWARE.get("camaras_duales"):
        log["h0"] = False
        d["h0"] = {"motivo": "coincidencia_en_2_camaras"}
    else:
        log["h0"] = IND
        d["h0"] = {"motivo": "una_camara_o_un_frame_no_prueba_ni_descarta_artefacto",
                   "single_frame": bool(det.get("single_frame")), "frames": int(det.get("frames") or 0)}

    # H1 aeronave. Absence of ADS-B match never rejects (non-transponder aircraft exist).
    if det.get("force_h1") and det.get("adsb_aircraft"):
        log["h1"] = True
        d["h1"] = {"forzado": True, "match": det["adsb_aircraft"], "nota": "sintetica: no es evidencia observacional"}
    elif origen == "simulacion":
        log["h1"] = IND
        d["h1"] = {"motivo": "sin_consulta_adsb_en_" + origen}
    else:
        lag = abs((datetime.now(timezone.utc) - t_utc).total_seconds())
        if lag > THRESHOLDS["h1_dt_s"] + 30:
            log["h1"] = IND
            d["h1"] = {"motivo": "snapshot_adsb_no_contemporaneo_sin_historico", "lag_s": round(lag, 1)}
        else:
            x = adsb_crosscheck(t_iso=t_utc.isoformat(), az_deg=az, el_deg=el,
                                sep_deg_max=THRESHOLDS["h1_sep_deg"], dt_s_max=THRESHOLDS["h1_dt_s"])
            m = x.get("matches") or []
            log["h1"] = True if m else IND
            d["h1"] = {"fuente": x.get("fuente", ""), "ok": x.get("ok", False), "matches": m[:3], "lag_s": round(lag, 1),
                       "motivo": "" if m else "sin_match_adsb_no_descarta_aeronave_sin_transpondedor"}

    # H2 satelite: min separation over t +/- h2_dt_s; only the given NORAD is checked.
    norad = int(det.get("norad_hint") or 25544)
    if det.get("force_h2"):
        log["h2"] = True
        d["h2"] = {"forzado": True, "norad": norad, "nota": "sintetica: no es evidencia observacional"}
    else:
        try:
            best = None
            n = int(THRESHOLDS["h2_dt_s"])
            for k in range(-n, n + 1):
                s = satellite_azel_at(t_utc + timedelta(seconds=k), norad=norad)
                sep = angular_sep_azel_deg(az, el, s["az_deg"], s["el_deg"])
                if best is None or sep < best[0]:
                    best = (sep, k, s)
            sep, k, s = best
            hit = sep < THRESHOLDS["h2_sep_deg"] and s["el_deg"] > 0
            log["h2"] = True if hit else IND
            d["h2"] = {"norad": norad, "sep_min_deg": round(sep, 4), "dt_s_at_min": k,
                       "sat_az_deg": round(s["az_deg"], 3), "sat_el_deg": round(s["el_deg"], 3),
                       "sat_sunlit": s.get("sunlit"),
                       "motivo": "" if hit else f"solo_norad_{norad}_comprobado_otros_satelites_sin_catalogo"}
            if hit and s.get("sunlit") is False:
                d["h2"]["aviso"] = "satelite_en_sombra: coincidencia solo geometrica, no observable opticamente"
        except Exception as exc:  # noqa: BLE001
            log["h2"] = IND
            d["h2"] = {"motivo": "tle_no_disponible", "error": str(exc)[:200]}

    # H3 astro: Sun/Moon/planets only; no star catalogue.
    h3 = check_h3(az, el, t_utc, sep_max=THRESHOLDS["h3_sep_deg"])
    log["h3"] = True if h3.get("matched") else IND
    d["h3"] = {**h3, "motivo": "" if h3.get("matched") else "sin_catalogo_estelar_solo_sol_luna_planetas"}

    # H4 deriva de viento
    w = det.get("wind_drift_error_pct")
    if w is None:
        log["h4"] = IND
        d["h4"] = {"motivo": "sin_serie_temporal_ni_perfil_viento"}
    else:
        log["h4"] = abs(float(w)) <= THRESHOLDS["h4_wind_tol"] * 100.0
        d["h4"] = {"wind_drift_error_pct": float(w), "tol_pct": THRESHOLDS["h4_wind_tol"] * 100.0}

    # H5 objeto cercano: needs parallax (dual cameras)
    if det.get("parallax_high") is not None and HARDWARE.get("camaras_duales"):
        log["h5"] = bool(det["parallax_high"]) or bool(det.get("size_angular_incoherent"))
        d["h5"] = {"parallax_high": bool(det["parallax_high"])}
    elif det.get("size_angular_incoherent"):
        log["h5"] = True
        d["h5"] = {"size_angular_incoherent": True}
    else:
        log["h5"] = IND
        d["h5"] = {"motivo": "sin_paralaje_medido"}

    # H6 meteoro
    dur, lin = det.get("duration_s"), det.get("trajectory_linear")
    if dur is None or lin is None:
        log["h6"] = IND
        d["h6"] = {"motivo": "duracion_o_linealidad_desconocida"}
    else:
        log["h6"] = float(dur) < THRESHOLDS["h6_max_duration_s"] and bool(lin)
        d["h6"] = {"duration_s": float(dur), "trajectory_linear": bool(lin), "threshold_s": THRESHOLDS["h6_max_duration_s"]}

    # H7 optico
    og = det.get("optical_geometry_coherent")
    log["h7"] = True if og else IND
    d["h7"] = {"motivo": "geometria_optica_coherente" if og else "no_evaluado"}

    # H_kin: flag only, requires distances + errors + verified sync + dual cameras
    need = ["distance_m", "distance_err_m", "accel_g", "accel_err_g"]
    if HARDWARE.get("camaras_duales") and synced and all(det.get(k) is not None for k in need):
        lo = float(det["accel_g"]) - 3.0 * float(det["accel_err_g"])
        log["h_kin"] = lo > THRESHOLDS["h_kin_accel_g"]
        d["h_kin"] = {"accel_g": float(det["accel_g"]), "accel_err_g": float(det["accel_err_g"]), "accel_lo_3sigma_g": round(lo, 3),
                      "nota": "bandera_cinematica; no establece origen exotico"}
    else:
        log["h_kin"] = IND
        d["h_kin"] = {"motivo": "requiere_camaras_duales+sync_verificada+distancias_y_errores",
                      "faltan": [k for k in need if det.get(k) is None]}

    # H_mat
    if HARDWARE.get("espectro") or HARDWARE.get("polarimetria"):
        log["h_mat"] = IND if det.get("spectral_anomaly") is None else bool(det["spectral_anomaly"])
        d["h_mat"] = {"nota": "bandera; no establece origen"}
    else:
        log["h_mat"] = IND
        d["h_mat"] = {"motivo": "sin_sensor"}

    excluded = next((h for h in EXCLUDING if log[h] is True), "")
    if excluded:
        resultado = RESULT_BY_H[excluded]
    elif any(log[h] == IND for h in EXCLUDING):
        resultado = "no_identificado_insuficiente"
    else:
        resultado = "no_identificado_hipotesis_convencionales_descartadas_con_dato"
    flags = []
    if (d.get("h2") or {}).get("aviso"):
        flags.append("h2_coincidencia_geometrica_satelite_en_sombra")
    if log["h_kin"] is True:
        flags.append("cinematica_fuera_de_envolvente_requiere_revision")
    evidencia, nota = _evidence(origen, synced, det)
    risks = [f"{h}_indeterminado" for h in H_ORDER if log[h] == IND]
    return {
        "id": det.get("id") or "", "modo": modo, "origen": origen,
        "t_sync": synced, "t_sync_nota": "declarada+config; no verificada fisicamente" if synced else "",
        "conclusion_produccion": origen == "observacion_optica" and not det.get("force_h1") and not det.get("force_h2"),
        "evidencia_nota": nota,
        "t": t_utc.isoformat().replace("+00:00", "Z"), "az_deg": az, "el_deg": el,
        "station": {"lat_deg": STATION["lat_deg"], "lon_deg": STATION["lon_deg"], "coord_status": STATION["coord_status"]},
        "hardware_declarado": {k: HARDWARE[k] for k in ("camaras_duales", "gnss", "ntp")},
        "hipotesis": log, "detalles": d, "excluido_por": excluded, "resultado": resultado,
        "evidencia": evidencia, "banderas": flags, "anomaly_claim": False, "riesgos": risks,
        "orden_evaluacion": H_ORDER,
        "evaluado_at_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
    }
