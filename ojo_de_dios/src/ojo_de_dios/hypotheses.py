"""
Deterministic exclusion tree H0..H7 + H_kin + H_mat.

Order is fixed. First match excludes. All hypotheses are logged.
Evidence scale E0–E6 with hard caps:
  - without dual cameras + GNSS/NTP → max E3
  - without measured H_kin → never claim anomaly; stay at no_identificado_insuficiente
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .adsb import crosscheck as adsb_crosscheck
from .astro import check_h3
from .config import HARDWARE, STATION, THRESHOLDS
from .math_geo import angular_sep_azel_deg
from .tle import satellite_azel_at

MADRID = ZoneInfo("Europe/Madrid")
H_ORDER = ["h0", "h1", "h2", "h3", "h4", "h5", "h6", "h7", "h_kin", "h_mat"]


def _parse_t(t: str | None) -> datetime:
    if not t:
        return datetime.now(timezone.utc)
    s = t.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _cap_evidence(raw: str) -> str:
    """Apply hardware-based evidence ceiling."""
    order = ["E0", "E1", "E2", "E3", "E4", "E5", "E6"]
    max_allowed = "E3"
    if HARDWARE.get("camaras_duales") and HARDWARE.get("gnss") and HARDWARE.get("ntp"):
        max_allowed = "E6"
    if order.index(raw) > order.index(max_allowed):
        return max_allowed
    return raw


def evaluate_detection(det: dict[str, Any], modo: str = "experimento") -> dict[str, Any]:
    """
    Evaluate one detection through the exclusion tree.

    Expected detection fields (snake_case):
      id, t, az_deg, el_deg, duration_s, frames, single_camera, single_frame,
      parallax_high, size_angular_incoherent, wind_drift_error_pct,
      optical_geometry_coherent, accel_g (optional), spectral_anomaly (optional),
      norad_hint (optional), callsign_hint (optional)
    """
    log: dict[str, Any] = {h: False for h in H_ORDER}
    details: dict[str, Any] = {}
    t_utc = _parse_t(det.get("t"))
    az = float(det.get("az_deg", 0.0))
    el = float(det.get("el_deg", 0.0))
    duration_s = det.get("duration_s")
    excluded_by = ""
    resultado = ""
    evidencia = "E1"

    # --- H0 artefact ---
    h0 = bool(det.get("single_frame")) or (
        bool(det.get("single_camera", True)) and int(det.get("frames") or 0) <= 1
    )
    # Also treat explicit artefact flag
    if det.get("artefacto_sensor"):
        h0 = True
    log["h0"] = h0
    details["h0"] = {"single_frame": bool(det.get("single_frame")), "artefacto": bool(det.get("artefacto_sensor"))}
    if h0 and not excluded_by:
        excluded_by = "h0"
        resultado = "artefacto_sensor"
        evidencia = "E1"

    # --- H1 ADS-B aircraft ---
    if not excluded_by:
        matched = []
        adsb_meta = {"fuente": "", "ezy95fn_present": False}
        if det.get("force_h1") and det.get("adsb_aircraft"):
            matched = [det["adsb_aircraft"]]
            adsb_meta = {"fuente": det["adsb_aircraft"].get("fuente", "forced"), "ezy95fn_present": False}
        else:
            adsb = adsb_crosscheck(
                t_iso=det.get("t") or t_utc.isoformat(),
                az_deg=az,
                el_deg=el,
                sep_deg_max=THRESHOLDS["h1_sep_deg"],
                dt_s_max=THRESHOLDS["h1_dt_s"],
            )
            adsb_meta = adsb
            hint = (det.get("callsign_hint") or "").strip().upper().replace(" ", "")
            matched = list(adsb.get("matches") or [])
            if hint:
                for ac in adsb.get("nearest_airborne") or []:
                    fl = (ac.get("flight") or "").upper().replace(" ", "")
                    if fl == hint and ac.get("el_deg") is not None:
                        sep = angular_sep_azel_deg(az, el, ac["az_deg"], ac["el_deg"])
                        ac = {**ac, "sep_deg": round(sep, 4), "within_cone": sep < THRESHOLDS["h1_sep_deg"]}
                        if ac["within_cone"] and ac not in matched:
                            matched.append(ac)
        h1 = bool(matched)
        log["h1"] = h1
        details["h1"] = {
            "fuente": adsb_meta.get("fuente", ""),
            "matches": matched[:3],
            "sep_threshold_deg": THRESHOLDS["h1_sep_deg"],
            "dt_threshold_s": THRESHOLDS["h1_dt_s"],
            "ezy95fn_present": adsb_meta.get("ezy95fn_present", False),
        }
        if h1:
            excluded_by = "h1"
            resultado = "aeronave_identificada"
            evidencia = "E3" if modo == "experimento" else "E2"

    # --- H2 satellite TLE / SGP4 ---
    if not excluded_by:
        norad = int(det.get("norad_hint") or 25544)
        if det.get("force_h2"):
            h2 = True
            details["h2"] = {
                "norad": norad,
                "forced": True,
                "sep_threshold_deg": THRESHOLDS["h2_sep_deg"],
                "dt_threshold_s": THRESHOLDS["h2_dt_s"],
                "note": "force_h2 set (caller supplies known pass geometry)",
            }
        else:
            try:
                sat = satellite_azel_at(t_utc, norad=norad)
                sep = angular_sep_azel_deg(az, el, sat["az_deg"], sat["el_deg"])
                h2 = sep < THRESHOLDS["h2_sep_deg"] and sat["el_deg"] > 0
                details["h2"] = {
                    "norad": norad,
                    "sat_az_deg": round(sat["az_deg"], 4),
                    "sat_el_deg": round(sat["el_deg"], 4),
                    "sep_deg": round(sep, 4),
                    "sep_threshold_deg": THRESHOLDS["h2_sep_deg"],
                    "dt_threshold_s": THRESHOLDS["h2_dt_s"],
                    "tle_fuente": sat.get("tle_fuente", ""),
                }
            except Exception as exc:
                h2 = False
                details["h2"] = {"error": str(exc), "status": "PENDIENTE_DE_VERIFICACION"}
        log["h2"] = h2
        if h2:
            excluded_by = "h2"
            resultado = "satelite_identificado"
            evidencia = "E3" if modo == "experimento" else "E2"

    # --- H3 bright body ---
    if not excluded_by:
        h3res = check_h3(az, el, t_utc, sep_max=THRESHOLDS["h3_sep_deg"])
        h3 = bool(h3res.get("matched"))
        log["h3"] = h3
        details["h3"] = h3res
        if h3:
            excluded_by = "h3"
            resultado = "astro_identificado"
            evidencia = "E3" if modo == "experimento" else "E2"

    # --- H4 meteorological / balloon wind drift ---
    if not excluded_by:
        werr = det.get("wind_drift_error_pct")
        if werr is None:
            log["h4"] = False
            details["h4"] = {
                "status": "indeterminado",
                "note": "requiere serie temporal + perfil de viento; PENDIENTE_DE_VERIFICACION",
            }
        else:
            h4 = abs(float(werr)) <= THRESHOLDS["h4_wind_tol"] * 100.0 or abs(float(werr)) <= THRESHOLDS["h4_wind_tol"]
            # accept either fraction or percent
            if abs(float(werr)) <= 1.0:
                h4 = abs(float(werr)) <= THRESHOLDS["h4_wind_tol"]
            else:
                h4 = abs(float(werr)) <= THRESHOLDS["h4_wind_tol"] * 100.0
            log["h4"] = h4
            details["h4"] = {"wind_drift_error": werr, "tol": THRESHOLDS["h4_wind_tol"], "matched": h4}
            if h4:
                excluded_by = "h4"
                resultado = "meteo_o_globo"
                evidencia = "E2"

    # --- H5 bird/insect/drone nearby ---
    if not excluded_by:
        h5 = bool(det.get("parallax_high")) or bool(det.get("size_angular_incoherent"))
        if not HARDWARE.get("camaras_duales") and det.get("parallax_high") is None:
            log["h5"] = False
            details["h5"] = {
                "status": "indeterminado",
                "note": "sin camaras duales no hay paralaje; PENDIENTE_DE_VERIFICACION",
            }
        else:
            log["h5"] = h5
            details["h5"] = {
                "parallax_high": bool(det.get("parallax_high")),
                "size_angular_incoherent": bool(det.get("size_angular_incoherent")),
            }
            if h5:
                excluded_by = "h5"
                resultado = "objeto_cercano"
                evidencia = "E3"

    # --- H6 meteor / reentry ---
    if not excluded_by:
        linear = bool(det.get("trajectory_linear", False))
        h6 = False
        if duration_s is not None:
            h6 = float(duration_s) < THRESHOLDS["h6_max_duration_s"] and linear
        log["h6"] = h6
        details["h6"] = {
            "duration_s": duration_s,
            "trajectory_linear": linear,
            "threshold_s": THRESHOLDS["h6_max_duration_s"],
        }
        if h6:
            excluded_by = "h6"
            resultado = "meteoro_o_reentrada"
            evidencia = "E2"

    # --- H7 optical phenomenon ---
    if not excluded_by:
        h7 = bool(det.get("optical_geometry_coherent"))
        log["h7"] = h7
        details["h7"] = {"optical_geometry_coherent": h7}
        if h7:
            excluded_by = "h7"
            resultado = "fenomeno_optico"
            evidencia = "E2"

    # --- H_kin ---
    if HARDWARE.get("camaras_duales") and det.get("accel_g") is not None:
        h_kin = float(det["accel_g"]) > THRESHOLDS["h_kin_accel_g"]
        log["h_kin"] = h_kin
        details["h_kin"] = {"accel_g": det.get("accel_g"), "threshold_g": THRESHOLDS["h_kin_accel_g"]}
        if h_kin and not excluded_by:
            excluded_by = "h_kin"
            resultado = "cinematica_fuera_de_envolvente"
            evidencia = "E4"
    else:
        log["h_kin"] = False
        details["h_kin"] = {
            "status": "no_medible_sin_camara_dual",
            "note": "H_kin requiere triangulacion dual + tiempo sync",
        }

    # --- H_mat ---
    if HARDWARE.get("espectro") or HARDWARE.get("polarimetria"):
        h_mat = bool(det.get("spectral_anomaly"))
        log["h_mat"] = h_mat
        details["h_mat"] = {"spectral_anomaly": h_mat}
        if h_mat and not excluded_by:
            excluded_by = "h_mat"
            resultado = "firma_espectral_anomala"
            evidencia = "E4"
    else:
        log["h_mat"] = False
        details["h_mat"] = {"status": "sin_sensor"}

    if not excluded_by:
        resultado = "no_identificado_insuficiente"
        evidencia = "E1" if modo == "experimento" else "E2"
        # HARD RULE: never claim anomaly without measured H_kin
        details["anomaly_claim"] = False
        details["anomaly_rule"] = "sin H_kin medido no se declara anomalia"

    evidencia = _cap_evidence(evidencia)

    risks = []
    if details.get("h4", {}).get("status") == "indeterminado":
        risks.append("h4_no_descartable_sin_viento_serie")
    if details.get("h5", {}).get("status") == "indeterminado":
        risks.append("h5_no_descartable_sin_triangulacion")
    if details.get("h_kin", {}).get("status") == "no_medible_sin_camara_dual":
        risks.append("h_kin_no_medible")

    return {
        "id": det.get("id") or "",
        "modo": modo,
        "t": det.get("t") or t_utc.isoformat(),
        "az_deg": az,
        "el_deg": el,
        "station": {
            "lat_deg": STATION["lat_deg"],
            "lon_deg": STATION["lon_deg"],
            "coord_status": STATION["coord_status"],
        },
        "hardware": {
            "camaras_duales": HARDWARE["camaras_duales"],
            "gnss": HARDWARE["gnss"],
            "ntp": HARDWARE["ntp"],
        },
        "hipotesis": log,
        "detalles": details,
        "excluido_por": excluded_by,
        "resultado": resultado,
        "evidencia": evidencia,
        "riesgos": risks,
        "orden_evaluacion": H_ORDER,
        "evaluado_at_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
    }
