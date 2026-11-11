#!/usr/bin/env python3
"""
Vista "Ojo de Dios" para la beta NNC.

Autoría: Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia IA.

Reutiliza los procesos existentes del paquete ojo_de_dios (no los duplica):
  - adsb.get_adsb            ADS-B adsb.lol -> OpenSky -> airplanes.live
  - tle.predict_pass         Celestrak GP + SGP4 (skyfield) + visibility.classify_passes
  - meteo.get_meteo          Open-Meteo -> MET Norway -> cache caducada
  - hypotheses.evaluate_detection  cadena H0..H7 + H_kin + H_mat tri-estado, E0..E6 con tope por origen

Reglas de esta vista:
  - No inventa detecciones. Sin cámara/feeds reales -> "sin detecciones ópticas reales".
  - Nunca declara FANI. Estados posibles: EXPLICADO | no_explicado_pendiente | indeterminado.
  - Objetos de catálogo (ADS-B, TLE) -> origen sintetica_desde_catalogo -> evidencia <= E2.
  - Silencio ADS-B (baliza que deja de verse) = indeterminado, nunca anomalía.
  - Aviso solo si hay desviación medible: residuo > K_SIGMA * sigma respecto a lo predicho.
  - v = ω·R solo si R es una distancia MEDIDA por la estación; si no, solo ω y R = "".
Umbrales y sigmas: valores iniciales PENDIENTE_DE_VERIFICACION (sin calibrar con datos de campo).
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

AUTORIA = "Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia IA"
_HERE = Path(__file__).resolve().parent


def _resolver_ojo_src() -> str:
    """OJO_DE_DIOS_SRC (env) -> <repo>/ojo_de_dios/src (NNC/build-beta/../../) -> ../ojo_de_dios/src (copia suelta)."""
    env = os.environ.get("OJO_DE_DIOS_SRC", "")
    cands = [Path(env)] if env else []
    cands += [_HERE.parents[1] / "ojo_de_dios" / "src", _HERE.parent / "ojo_de_dios" / "src"]
    for c in cands:
        if (c / "ojo_de_dios" / "__init__.py").exists():
            return str(c)
    return str(cands[0]) if cands else ""


OJO_SRC = _resolver_ojo_src()
if OJO_SRC and OJO_SRC not in sys.path:
    sys.path.insert(0, OJO_SRC)

IMPORT_ERROR = ""
try:
    from ojo_de_dios import adsb as adsb_mod
    from ojo_de_dios import meteo as meteo_mod
    from ojo_de_dios import tle as tle_mod
    from ojo_de_dios import hypotheses as hy
    from ojo_de_dios.config import HARDWARE, STATION, THRESHOLDS
    from ojo_de_dios.math_geo import angular_sep_azel_deg, haversine_km, wgs84_to_ecef
    DISPONIBLE = True
except Exception as exc:  # noqa: BLE001
    DISPONIBLE = False
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"[:300]

MADRID = ZoneInfo("Europe/Madrid")
HERE = _HERE
DATA = Path(os.environ.get("NNC_OJO_DATA", str(HERE / "data")))
HIST_FILE = DATA / "historial_ojo.jsonl"
DET_FILE = DATA / "detecciones_opticas.jsonl"  # solo detecciones REALES de cámara; vacío -> ninguna
ISS_OBS_URL = "https://api.wheretheiss.at/v1/satellites/25544"
UA = {"User-Agent": "NNC-OjoDeDios/1.0 (ElPrat; local-dev)"}

ADSB_RADIUS_NM = 50.0          # mismo radio que hypotheses.crosscheck -> H1 cruza contra el mismo snapshot
RADIO_MAX_KM = round(ADSB_RADIUS_NM * 1.852, 1)  # 92.6 km
K_SIGMA = 3.0
# Modelo de incertidumbre (PENDIENTE_DE_VERIFICACION)
SIGMA_POS_ADSB_KM = 0.2        # error de posición ADS-B asumido
SIGMA_LATENCIA_S = 10.0        # latencia de posición desconocida (seen_pos no se conserva)
SIGMA_V_FRAC = 0.10            # cambio de velocidad/rumbo no modelado
DT_MIN_S, DT_MAX_S = 5.0, 180.0
SIGMA_ISS_KM_BASE = 2.0        # SGP4 vs fuente independiente
SIGMA_ISS_KM_POR_DIA = 2.0
ESTADOS = ("EXPLICADO", "no_explicado_pendiente", "indeterminado")
E_ORDER = ["E0", "E1", "E2", "E3", "E4", "E5", "E6"]
CAP_ORIGEN = {"sintetica_desde_catalogo": "E2", "simulacion": "E2", "observacion_optica": "E6"}

DEFAULT_FILTROS: dict[str, float] = {
    "radio_km": RADIO_MAX_KM, "alt_min_ft": 0.0, "alt_max_ft": 60000.0,
    "el_min_deg": 0.0, "edad_max_s": 120.0,
}
LIMITES = {
    "radio_km": (0.1, RADIO_MAX_KM), "alt_min_ft": (-1500.0, 100000.0), "alt_max_ft": (0.0, 100000.0),
    "el_min_deg": (-5.0, 89.0), "edad_max_s": (1.0, 3600.0),
}


def now_madrid() -> str:
    return datetime.now(MADRID).isoformat(timespec="seconds")


# ---------------------------------------------------------------- funciones puras
def parse_filtros(qs: dict[str, Any] | None) -> dict[str, float]:
    """Validación estricta: desconocido -> ValueError; fuera de rango -> ValueError."""
    f = dict(DEFAULT_FILTROS)
    for k, v in (qs or {}).items():
        if isinstance(v, list):
            v = v[0] if v else ""
        if k not in DEFAULT_FILTROS:
            raise ValueError(f"filtro desconocido: {k}")
        if v in ("", None):
            continue
        try:
            x = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{k} no numérico") from exc
        if not math.isfinite(x):
            raise ValueError(f"{k} no finito")
        lo, hi = LIMITES[k]
        if not lo <= x <= hi:
            raise ValueError(f"{k} fuera de [{lo},{hi}]")
        f[k] = x
    if f["alt_min_ft"] > f["alt_max_ft"]:
        raise ValueError("alt_min_ft > alt_max_ft")
    return f


def aplicar_filtros(aircraft: list[dict[str, Any]], f: dict[str, float]) -> tuple[list[dict], list[dict]]:
    """Estricto: si un campo necesario para el filtro es desconocido, se descarta (con motivo)."""
    ok, fuera = [], []
    for a in aircraft:
        motivo = ""
        if a.get("on_ground"):
            motivo = "en_tierra"
        elif a.get("dist_km") is None or a["dist_km"] > f["radio_km"]:
            motivo = "fuera_de_radio"
        elif a.get("alt_ft") is None:
            motivo = "altitud_desconocida"
        elif not f["alt_min_ft"] <= a["alt_ft"] <= f["alt_max_ft"]:
            motivo = "fuera_de_altitud"
        elif a.get("el_deg") is None:
            motivo = "elevacion_desconocida"
        elif a["el_deg"] < f["el_min_deg"]:
            motivo = "bajo_elevacion_minima"
        (fuera if motivo else ok).append(a if not motivo else {"hex": a.get("hex", ""), "flight": a.get("flight", ""), "motivo": motivo})
    return ok, fuera


def omega_r(omega_rad_s: float | None, r_medida_m: float | None) -> dict[str, Any]:
    """v_tan = ω·R solo con R medida por la estación (>0, finita). Si no: R = "" y v = ""."""
    om = "" if omega_rad_s is None or not math.isfinite(float(omega_rad_s)) else float(omega_rad_s)
    if r_medida_m is None or r_medida_m == "" or not math.isfinite(float(r_medida_m)) or float(r_medida_m) <= 0 or om == "":
        return {"omega_rad_s": om, "R_m": "", "v_tan_m_s": "", "nota": "sin_R_medida_no_se_calcula_v"}
    return {"omega_rad_s": om, "R_m": float(r_medida_m), "v_tan_m_s": om * float(r_medida_m), "nota": "v=omega*R_con_R_medida"}


def omega_desde_azel(az1: float, el1: float, az2: float, el2: float, dt_s: float) -> float | None:
    if dt_s is None or dt_s <= 0:
        return None
    return math.radians(angular_sep_azel_deg(az1, el1, az2, el2)) / dt_s


def destino(lat: float, lon: float, rumbo_deg: float, d_km: float) -> tuple[float, float]:
    R = 6371.0088
    p1, l1, th, dr = math.radians(lat), math.radians(lon), math.radians(rumbo_deg), d_km / R
    p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540.0) % 360.0 - 180.0


def _mean_track(t1: float, t2: float) -> float:
    x = math.cos(math.radians(t1)) + math.cos(math.radians(t2))
    y = math.sin(math.radians(t1)) + math.sin(math.radians(t2))
    return math.degrees(math.atan2(y, x)) % 360.0


def desviacion_aeronave(prev: dict[str, Any], cur: dict[str, Any], dt_s: float) -> dict[str, Any]:
    """Predicción por estima (velocidad y rumbo medios entre snapshots) vs posición reportada."""
    need = ("lat", "lon", "gs_kt", "track_deg")
    if not (DT_MIN_S <= dt_s <= DT_MAX_S) or any(prev.get(k) is None or cur.get(k) is None for k in need):
        return {"desviacion_medible": "indeterminado", "motivo": "sin_dos_epocas_validas_o_dt_fuera_de_rango", "dt_s": round(dt_s, 1)}
    v_kms = (float(prev["gs_kt"]) + float(cur["gs_kt"])) / 2.0 * 0.514444 / 1000.0
    lat_p, lon_p = destino(prev["lat"], prev["lon"], _mean_track(prev["track_deg"], cur["track_deg"]), v_kms * dt_s)
    res = haversine_km(lat_p, lon_p, cur["lat"], cur["lon"])
    sigma = math.sqrt(2 * SIGMA_POS_ADSB_KM ** 2 + (v_kms * SIGMA_LATENCIA_S) ** 2 + (SIGMA_V_FRAC * v_kms * dt_s) ** 2)
    return {"desviacion_medible": res > K_SIGMA * sigma, "residuo_km": round(res, 3), "sigma_km": round(sigma, 3),
            "k_sigma": K_SIGMA, "n_sigma": round(res / sigma, 2), "dt_s": round(dt_s, 1),
            "pred_lat": round(lat_p, 5), "pred_lon": round(lon_p, 5), "modelo": "estima_rumbo_y_gs_medios"}


def desviacion_iss(pred_ecef: dict[str, float], obs_ecef: dict[str, float], tle_age_d: float | None) -> dict[str, Any]:
    if tle_age_d is None:
        return {"desviacion_medible": "indeterminado", "motivo": "edad_tle_desconocida"}
    d_km = math.dist((pred_ecef["x_m"], pred_ecef["y_m"], pred_ecef["z_m"]), (obs_ecef["x_m"], obs_ecef["y_m"], obs_ecef["z_m"])) / 1000.0
    sigma = SIGMA_ISS_KM_BASE + SIGMA_ISS_KM_POR_DIA * max(0.0, tle_age_d)
    return {"desviacion_medible": d_km > K_SIGMA * sigma, "residuo_km": round(d_km, 3), "sigma_km": round(sigma, 3),
            "k_sigma": K_SIGMA, "n_sigma": round(d_km / sigma, 2), "modelo": "SGP4_celestrak_vs_wheretheiss_at"}


def silencio_adsb(prev_hex: set[str], cur_hex: set[str]) -> list[dict[str, Any]]:
    return [{"hex": h, "estado": "indeterminado", "motivo": "silencio_adsb_no_es_anomalia", "aviso": False}
            for h in sorted(prev_hex - cur_hex)]


def estado_desde_resultado(r: dict[str, Any]) -> str:
    """Mapa cadena -> estado de vista. Nunca FANI."""
    if r.get("excluido_por"):
        return "EXPLICADO"
    return "no_explicado_pendiente"


def cap_evidencia(origen: str, e: str) -> str:
    cap = CAP_ORIGEN.get(origen, "E0")
    if e not in E_ORDER:
        return "E0"
    return e if E_ORDER.index(e) <= E_ORDER.index(cap) else cap


def agrupar(objetos: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    g: dict[str, dict[str, int]] = {}
    for o in objetos:
        t = g.setdefault(o.get("tipo", "desconocido"), {})
        t[o.get("estado", "indeterminado")] = t.get(o.get("estado", "indeterminado"), 0) + 1
    return g


def resumen_cadena(r: dict[str, Any]) -> dict[str, Any]:
    return {"hipotesis": r.get("hipotesis", {}), "excluido_por": r.get("excluido_por", ""), "resultado": r.get("resultado", ""),
            "origen": r.get("origen", ""), "evidencia": cap_evidencia(r.get("origen", ""), r.get("evidencia", "E0")),
            "evidencia_nota": r.get("evidencia_nota", ""), "anomaly_claim": False}


def assert_sin_fani(obj: Any) -> None:
    """Garantía: ningún campo de estado/resultado contiene FANI confirmado."""
    s = json.dumps(obj, ensure_ascii=False).lower()
    for bad in ('"estado": "fani', '"resultado": "fani', '"fani_confirmado"', '"es_fani": true', '"anomaly_claim": true'):
        if bad in s:
            raise AssertionError("prohibido declarar FANI: " + bad)


# ---------------------------------------------------------------- fuentes (inyectables para tests)
def _http_json(url: str, timeout: float = 8.0) -> tuple[Any, Any]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        return e.code, None
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}", None


def _iss_sgp4(t_unix: float) -> dict[str, Any]:
    from skyfield.api import wgs84
    sat, meta = tle_mod._satellite_from_cache(25544)  # noqa: SLF001
    ts = tle_mod.LOADER.timescale()
    t = ts.from_datetime(datetime.fromtimestamp(t_unix, tz=timezone.utc))
    gp = wgs84.geographic_position_of(sat.at(t))
    return {"lat": float(gp.latitude.degrees), "lon": float(gp.longitude.degrees), "h_m": float(gp.elevation.m)}


FUENTES: dict[str, Callable[..., Any]] = {}
if DISPONIBLE:
    FUENTES = {
        "adsb": lambda: adsb_mod.get_adsb(radius_nm=ADSB_RADIUS_NM),
        "tle": lambda: tle_mod.predict_pass(norad=25544, hours=24.0, min_el_deg=10.0),
        "meteo": lambda: meteo_mod.get_meteo(),
        "iss_obs": lambda: _http_json(ISS_OBS_URL),
        "iss_sgp4": _iss_sgp4,
        "iss_now": lambda: tle_mod.satellite_azel_at(datetime.now(timezone.utc), norad=25544),
        "evaluar": lambda det: hy.evaluate_detection(det, modo="experimento"),
    }


class Estado:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.prev_ac: dict[str, dict[str, Any]] = {}
        self.prev_t: float | None = None
        self.tle_cache: tuple[float, dict[str, Any]] | None = None
        self.last_hist_t = 0.0


ESTADO = Estado()


def _leer_detecciones() -> list[dict[str, Any]]:
    if not DET_FILE.exists():
        return []
    out = []
    for ln in DET_FILE.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if d.get("origen") == "observacion_optica":
                out.append(d)
    return out


def construir_vista(filtros: dict[str, float] | None = None, fuentes: dict[str, Callable] | None = None,
                    estado: Estado | None = None, guardar: bool = True) -> dict[str, Any]:
    t_wall = time.time()
    if not DISPONIBLE and fuentes is None:
        return {"ok": False, "error": "modulo_ojo_de_dios_no_disponible", "detalle": IMPORT_ERROR, "autoria": AUTORIA}
    F = fuentes or FUENTES
    st = estado or ESTADO
    f = filtros or dict(DEFAULT_FILTROS)
    now_utc = datetime.now(timezone.utc)
    t_iso = now_utc.isoformat()
    fuentes_estado: dict[str, Any] = {}
    objetos: list[dict[str, Any]] = []
    avisos: list[dict[str, Any]] = []
    errores: list[str] = []

    # --- ADS-B
    try:
        snap = F["adsb"]()
    except Exception as exc:  # noqa: BLE001
        snap = {"ok": False, "fuente": "", "http_status": f"error:{type(exc).__name__}", "aircraft": []}
    snap_t = float(snap.get("_cached_at") or 0.0) or None
    edad_adsb = None if snap_t is None else round(max(0.0, time.time() - snap_t), 1)
    fuentes_estado["adsb"] = {"ok": bool(snap.get("ok")), "fuente": snap.get("fuente", ""), "http_status": snap.get("http_status", ""),
                              "fallbacks_tried": snap.get("fallbacks_tried", []), "edad_s": "" if edad_adsb is None else edad_adsb,
                              "fetched_at_madrid": snap.get("fetched_at_madrid", ""), "radius_nm": snap.get("radius_nm", ADSB_RADIUS_NM),
                              "n_total": len(snap.get("aircraft") or []), "cadena": "adsb.lol -> OpenSky -> airplanes.live"}
    aircraft = snap.get("aircraft") or [] if snap.get("ok") else []
    adsb_valido = bool(snap.get("ok")) and edad_adsb is not None and edad_adsb <= f["edad_max_s"]
    if snap.get("ok") and not adsb_valido:
        fuentes_estado["adsb"]["descartado"] = "dato_mas_antiguo_que_edad_max_s"
    kept, fuera = aplicar_filtros(aircraft if adsb_valido else [], f)
    cur_map = {a["hex"]: a for a in aircraft if a.get("hex")} if adsb_valido else {}
    dt_snap = None if (st.prev_t is None or snap_t is None) else snap_t - st.prev_t
    nuevo_snapshot = dt_snap is not None and dt_snap > 0.5

    for a in kept:
        det = {"id": a.get("flight") or a.get("hex"), "t": t_iso, "az_deg": float(a["az_deg"]) % 360.0, "el_deg": float(a["el_deg"]),
               "origen": "sintetica_desde_catalogo", "callsign_hint": a.get("flight", "")}
        try:
            r = F["evaluar"](det)
            cad = resumen_cadena(r)
            est = estado_desde_resultado(r)
        except Exception as exc:  # noqa: BLE001
            cad = {"error": str(exc)[:160], "evidencia": "E0", "anomaly_claim": False}
            est = "indeterminado"
        o: dict[str, Any] = {"tipo": "aeronave_adsb", "id": a.get("flight") or a.get("hex"), "hex": a.get("hex", ""), "flight": a.get("flight", ""),
                             "lat": a["lat"], "lon": a["lon"], "alt_ft": a["alt_ft"], "alt_datum": a.get("alt_datum", ""),
                             "dist_km": a["dist_km"], "slant_km_baliza": a.get("slant_km"), "az_deg": a["az_deg"], "el_deg": a["el_deg"],
                             "gs_kt": a.get("gs_kt"), "v_baliza_m_s": None if a.get("gs_kt") is None else round(float(a["gs_kt"]) * 0.514444, 1),
                             "track_deg": a.get("track_deg"), "estado": est, "cadena": cad,
                             "motivo_estado": "baliza_adsb_coincidente_h1" if est == "EXPLICADO" else "cadena_sin_exclusion_ver_hipotesis"}
        p = st.prev_ac.get(a.get("hex", ""))
        if nuevo_snapshot and p and p.get("el_deg") is not None:
            om = omega_desde_azel(p["az_deg"], p["el_deg"], a["az_deg"], a["el_deg"], dt_snap)
            o["cinematica"] = omega_r(om, None)  # R de baliza NO es R medida por la estación
            dv = desviacion_aeronave(p, a, dt_snap)
        else:
            o["cinematica"] = omega_r(None, None)
            dv = {"desviacion_medible": "indeterminado", "motivo": "primera_epoca_o_snapshot_repetido"}
        o["desviacion"] = dv
        if dv.get("desviacion_medible") is True:
            avisos.append({"tipo": "desviacion_aeronave", "id": o["id"], "residuo_km": dv["residuo_km"], "sigma_km": dv["sigma_km"],
                           "n_sigma": dv["n_sigma"], "estado": est,
                           "nota": "desviacion respecto a prediccion por estima; con baliza sigue EXPLICADO; no es FANI"})
        objetos.append(o)

    silencios = silencio_adsb(set(st.prev_ac), set(cur_map)) if (nuevo_snapshot and adsb_valido) else []
    if not snap.get("ok"):
        silencios_global = {"estado": "indeterminado", "motivo": "sin_fuente_adsb_disponible_no_es_anomalia"}
    else:
        silencios_global = {}

    # --- TLE / ISS (cache 60 s del cálculo de pases)
    try:
        if st.tle_cache and t_wall - st.tle_cache[0] < 60:
            tp = st.tle_cache[1]
        else:
            tp = F["tle"]()
            st.tle_cache = (t_wall, tp)
    except Exception as exc:  # noqa: BLE001
        tp = {"ok": False, "error": str(exc)[:160]}
        errores.append("tle:" + str(exc)[:100])
    fuentes_estado["tle"] = {"ok": bool(tp.get("ok")), "fuente": tp.get("tle_fuente", ""), "http_status": tp.get("tle_http_status", ""),
                             "tle_epoch_utc": tp.get("tle_epoch_utc", ""), "edad_tle_h": tp.get("tle_age_h", ""),
                             "edad_s": "" if tp.get("tle_age_h") in (None, "") else round(float(tp["tle_age_h"]) * 3600.0, 0),
                             "edad_nota": "edad del epoch TLE (no de la descarga)",
                             "cache_hit": tp.get("tle_cache_hit", ""), "cadena": "celestrak -> TLE local (cache)"}
    iss_obj: dict[str, Any] = {}
    if tp.get("ok"):
        now = tp.get("now") or {}
        if "iss_now" in F:  # posición actual recalculada (los pases se cachean 60 s, la posición no)
            try:
                s_now = F["iss_now"]()
                now = {"az_deg": s_now["az_deg"], "el_deg": s_now["el_deg"], "range_km": s_now["range_km"], "sunlit": s_now.get("sunlit")}
            except Exception as exc:  # noqa: BLE001
                errores.append("iss_now:" + str(exc)[:100])
        el = float(now.get("el_deg", -90.0))
        det = {"id": "ISS_25544", "t": t_iso, "az_deg": float(now.get("az_deg", 0.0)) % 360.0, "el_deg": el,
               "origen": "sintetica_desde_catalogo", "norad_hint": 25544}
        if el <= 0:
            det["force_h2"] = True  # bajo horizonte: identidad por catálogo (permitido solo en origen catálogo)
        try:
            r = F["evaluar"](det)
            cad, est = resumen_cadena(r), estado_desde_resultado(r)
        except Exception as exc:  # noqa: BLE001
            cad, est = {"error": str(exc)[:160], "evidencia": "E0", "anomaly_claim": False}, "indeterminado"
        pases = tp.get("pases") or []
        iss_obj = {"tipo": "satelite_tle", "id": "ISS (NORAD 25544)", "az_deg": round(float(now.get("az_deg", 0.0)), 3), "el_deg": round(el, 3),
                   "range_km_sgp4": None if now.get("range_km") is None else round(float(now["range_km"]), 1),
                   "iluminada": now.get("sunlit", ""), "sobre_horizonte": el > 0, "estado": est, "cadena": cad,
                   "motivo_estado": "catalogo_tle_h2" + ("_forzado_bajo_horizonte" if el <= 0 else ""),
                   "cinematica": omega_r(None, None),
                   "pases_24h": [{k: p.get(k, "") for k in ("rise_madrid", "culm_madrid", "set_madrid", "culm_az_deg", "culm_el_deg",
                                                             "clase", "visible_start_madrid", "visible_end_madrid", "visible_max_el_deg",
                                                             "sunlit_fraction", "motivos", "confianza_orbita", "brillo")} for p in pases],
                   "n_pases": len(pases), "n_potencialmente_visible_optico": sum(1 for p in pases if p.get("clase") == "potencialmente_visible_optico"),
                   "criterio_visibilidad": tp.get("criterio_visibilidad", {})}
        # desviación medible ISS: SGP4 vs fuente independiente (wheretheiss.at)
        code, js = F["iss_obs"]()
        fuentes_estado["iss_obs"] = {"ok": js is not None, "fuente": "wheretheiss_at", "http_status": code}
        if js and all(k in js for k in ("latitude", "longitude", "altitude", "timestamp")):
            fuentes_estado["iss_obs"]["edad_s"] = round(max(0.0, time.time() - float(js["timestamp"])), 1)
            fuentes_estado["iss_obs"]["nota_reloj"] = "reloj local sin GNSS/NTP verificado; edad negativa se recorta a 0"
            try:
                pr = F["iss_sgp4"](float(js["timestamp"]))
                pe = wgs84_to_ecef(pr["lat"], pr["lon"], pr["h_m"])
                oe = wgs84_to_ecef(float(js["latitude"]), float(js["longitude"]), float(js["altitude"]) * 1000.0)
                age_h = tp.get("tle_age_h")
                dv = desviacion_iss(pe, oe, None if age_h in (None, "") else float(age_h) / 24.0)
                dv.update({"obs_lat": round(float(js["latitude"]), 4), "obs_lon": round(float(js["longitude"]), 4),
                           "pred_lat": round(float(pr["lat"]), 4), "pred_lon": round(float(pr["lon"]), 4)})
                iss_obj.update({"lat": float(js["latitude"]), "lon": float(js["longitude"]), "alt_km": float(js["altitude"])})
            except Exception as exc:  # noqa: BLE001
                dv = {"desviacion_medible": "indeterminado", "motivo": "error_sgp4:" + str(exc)[:80]}
        else:
            dv = {"desviacion_medible": "indeterminado", "motivo": "fuente_independiente_no_disponible"}
        iss_obj["desviacion"] = dv
        if dv.get("desviacion_medible") is True:
            avisos.append({"tipo": "desviacion_iss", "id": "ISS", "residuo_km": dv["residuo_km"], "sigma_km": dv["sigma_km"],
                           "n_sigma": dv["n_sigma"], "estado": iss_obj["estado"],
                           "nota": "discrepancia entre fuentes de catalogo; ISS sigue EXPLICADO; no es FANI"})
        objetos.append(iss_obj)

    # --- Meteo
    try:
        m = F["meteo"]()
    except Exception as exc:  # noqa: BLE001
        m = {"ok": False, "fuente": "", "http_status": f"error:{type(exc).__name__}"}
    fuentes_estado["meteo"] = {"ok": bool(m.get("ok")), "fuente": m.get("fuente", ""), "http_status": m.get("http_status", ""),
                               "edad_s": m.get("cache_age_s", 0.0) if m.get("cache_hit") else 0.0, "stale": bool(m.get("stale")),
                               "fetched_at_madrid": m.get("original_fetched_at_madrid") or m.get("fetched_at_madrid", ""),
                               "cadena": "open-meteo -> MET Norway -> cache caducada"}
    meteo_out = {k: m.get(k, "") for k in ("cloud_cover_pct", "visibility_m", "wind_speed_10m", "wind_speed_unit", "wind_direction_10m_deg", "api_time", "naturaleza")}
    meteo_out["nota"] = "modelo/pronostico, no observacion del cielo"

    # --- Detecciones ópticas reales (solo si existen)
    dets = _leer_detecciones()
    det_out = []
    for d in dets:
        try:
            r = F["evaluar"]({k: d[k] for k in d if k in ("id", "t", "az_deg", "el_deg", "duration_s", "frames", "origen", "single_frame", "t_sync")})
            det_out.append({"tipo": "deteccion_optica", "id": d.get("id", ""), "estado": estado_desde_resultado(r), "cadena": resumen_cadena(r)})
        except Exception as exc:  # noqa: BLE001
            det_out.append({"tipo": "deteccion_optica", "id": d.get("id", ""), "estado": "indeterminado", "error": str(exc)[:160]})
    objetos.extend(det_out)

    # --- actualizar estado
    if adsb_valido and snap_t is not None and (st.prev_t is None or snap_t != st.prev_t):
        st.prev_ac, st.prev_t = cur_map, snap_t

    e_max = "E0"
    for o in objetos:
        e = (o.get("cadena") or {}).get("evidencia", "E0")
        if e in E_ORDER and E_ORDER.index(e) > E_ORDER.index(e_max):
            e_max = e
    out = {
        "ok": True, "proyecto": "ojo_de_dios_nnc_beta", "autoria": AUTORIA,
        "generado_utc": t_iso.replace("+00:00", "Z"), "generado_madrid": now_madrid(),
        "estacion": {"lat_deg": STATION["lat_deg"], "lon_deg": STATION["lon_deg"], "h_ell_m": STATION["h_ell_m"], "coord_status": STATION["coord_status"]} if DISPONIBLE else {},
        "hardware_declarado": {k: HARDWARE.get(k) for k in ("camaras", "camaras_duales", "gnss", "ntp", "lora")} if DISPONIBLE else {},
        "filtros": f, "fuentes": fuentes_estado,
        "detecciones_opticas": det_out,
        "detecciones_opticas_nota": "" if det_out else "sin detecciones ópticas reales (no hay cámara ni feed conectado)",
        "objetos": objetos, "descartados_por_filtro": fuera, "n_descartados": len(fuera),
        "silencio_adsb": silencios, "silencio_adsb_global": silencios_global,
        "grupos": agrupar(objetos), "avisos": avisos,
        "avisos_nota": "solo desviacion medible (residuo > %g sigma); silencio ADS-B no genera aviso" % K_SIGMA,
        "meteo": meteo_out, "evidencia_max_mostrada": e_max,
        "evidencia_nota": "objetos de catalogo (ADS-B/TLE) = sintetica_desde_catalogo -> tope E2; no es observacion optica",
        "estados_posibles": list(ESTADOS), "fani_declarado": False,
        "modelo_incertidumbre": {"sigma_pos_adsb_km": SIGMA_POS_ADSB_KM, "sigma_latencia_s": SIGMA_LATENCIA_S, "sigma_v_frac": SIGMA_V_FRAC,
                                 "sigma_iss_km": f"{SIGMA_ISS_KM_BASE}+{SIGMA_ISS_KM_POR_DIA}*edad_tle_d", "k_sigma": K_SIGMA,
                                 "status": "PENDIENTE_DE_VERIFICACION"},
        "errores": errores, "calculo_s": round(time.time() - t_wall, 2),
    }
    assert_sin_fani(out)
    if guardar:
        _historial(out, st)
    return out


def _historial(v: dict[str, Any], st: Estado) -> None:
    if time.time() - st.last_hist_t < 25:
        return
    st.last_hist_t = time.time()
    DATA.mkdir(parents=True, exist_ok=True)
    row = {"t_madrid": v["generado_madrid"], "t_utc": v["generado_utc"], "grupos": v["grupos"], "avisos": v["avisos"],
           "n_silencio_adsb": len(v["silencio_adsb"]), "evidencia_max": v["evidencia_max_mostrada"],
           "fuentes": {k: {"ok": s.get("ok"), "fuente": s.get("fuente"), "http_status": s.get("http_status"), "edad_s": s.get("edad_s", "")}
                       for k, s in v["fuentes"].items()},
           "filtros": v["filtros"], "fani_declarado": False}
    with HIST_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def leer_historial(n: int = 50) -> list[dict[str, Any]]:
    if not HIST_FILE.exists():
        return []
    lines = HIST_FILE.read_text(encoding="utf-8").splitlines()[-max(1, min(n, 500)):]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def vista_segura(qs: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    try:
        f = parse_filtros(qs)
    except ValueError as exc:
        return 422, {"ok": False, "error": str(exc), "autoria": AUTORIA}
    with ESTADO.lock:
        try:
            return 200, construir_vista(f)
        except Exception as exc:  # noqa: BLE001
            return 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300], "autoria": AUTORIA}


if __name__ == "__main__":
    code, body = vista_segura({})
    print(json.dumps(body, ensure_ascii=False, indent=1)[:6000])
    sys.exit(0 if code == 200 else 1)
