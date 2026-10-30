"""FastAPI REST surface for Ojo de Dios / NNC Consola v2."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from . import adsb as adsb_mod
from . import meteo as meteo_mod
from . import tle as tle_mod
from .ags_lora import ags_core_supervisor_message, pack_lora_uplink
from .config import EVIDENCE_RULES, HARDWARE, STATION, STATE, THRESHOLDS
from .hypotheses import evaluate_detection
from .math_geo import equations_doc, sha256_canonical, wgs84_to_ecef

MADRID = ZoneInfo("Europe/Madrid")

app = FastAPI(title="Ojo de Dios / NNC Consola", version="2.0.0")


class EcefAuditIn(BaseModel):
    lat_deg: float
    lon_deg: float
    h_m: float = 0.0
    t: str = ""
    id: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class HypothesesIn(BaseModel):
    id: str = ""
    t: str = ""
    az_deg: float
    el_deg: float
    duration_s: Optional[float] = None
    frames: int = 0
    single_frame: bool = False
    single_camera: bool = True
    artefacto_sensor: bool = False
    callsign_hint: str = ""
    norad_hint: Optional[int] = None
    force_h1: bool = False
    force_h2: bool = False
    adsb_aircraft: Optional[dict[str, Any]] = None
    wind_drift_error_pct: Optional[float] = None
    parallax_high: Optional[bool] = None
    size_angular_incoherent: bool = False
    trajectory_linear: bool = False
    optical_geometry_coherent: bool = False
    accel_g: Optional[float] = None
    spectral_anomaly: bool = False
    modo: str = "experimento"


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    return {
        "proyecto": "ojo_de_dios_nnc",
        "version": "2.0",
        "modo": STATE.modo,
        "estacion": STATION,
        "hardware": HARDWARE,
        "thresholds": THRESHOLDS,
        "evidence_rules": EVIDENCE_RULES,
        "equations": equations_doc(),
        "sources_last": STATE.sources_last,
        "live_probes": STATE.live_probes,
        "time_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
        "ags_lora": {
            "hardware": False,
            "schema": "ojo_de_dios_lora_v1",
            "status": "PENDIENTE_DE_VERIFICACION",
        },
    }


@app.post("/api/v1/audit/ecef")
def audit_ecef(body: EcefAuditIn) -> dict[str, Any]:
    ecef = wgs84_to_ecef(body.lat_deg, body.lon_deg, body.h_m)
    canonical_in = {
        "lat_deg": body.lat_deg,
        "lon_deg": body.lon_deg,
        "h_m": body.h_m,
        "t": body.t,
        "id": body.id,
        "extra": body.extra,
    }
    digest = sha256_canonical(canonical_in)
    return {
        "ok": True,
        "input": canonical_in,
        "input_sha256": digest,
        "ecef": ecef,
        "wgs84": {"a_m": 6378137.0, "f": "1/298.257223563"},
        "equations": equations_doc()["wgs84_to_ecef"],
        "coord_status": STATION["coord_status"],
        "time_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
    }


@app.get("/api/v1/radar")
def radar(t: str = Query(default="")) -> dict[str, Any]:
    """Known-object az/el view: ADS-B nearest + ISS now/next pass."""
    snap = adsb_mod.get_adsb()
    iss = tle_mod.predict_pass(norad=25544, hours=12.0, min_el_deg=10.0)
    airborne = [
        {
            "type": "aircraft",
            "flight": a.get("flight") or "",
            "hex": a.get("hex") or "",
            "az_deg": a.get("az_deg"),
            "el_deg": a.get("el_deg"),
            "dist_km": a.get("dist_km"),
            "alt_ft": a.get("alt_ft"),
        }
        for a in (snap.get("aircraft") or [])
        if not a.get("on_ground") and a.get("el_deg") is not None and (a.get("alt_ft") or 0) > 0 and (a.get("el_deg") or -1) > 0
    ][:20]
    return {
        "t_query": t or datetime.now(timezone.utc).isoformat(),
        "time_madrid": datetime.now(MADRID).isoformat(timespec="seconds"),
        "station": {"lat_deg": STATION["lat_deg"], "lon_deg": STATION["lon_deg"], "coord_status": STATION["coord_status"]},
        "adsb_fuente": snap.get("fuente") or "",
        "adsb_http_status": snap.get("http_status") or "",
        "aircraft": airborne,
        "iss": {
            "now": iss.get("now") or {},
            "next_culmination": iss.get("next_culmination") or {},
            "tle_epoch": iss.get("tle_epoch") or "",
        },
    }


@app.post("/api/v1/hypotheses/check")
def hypotheses_check(body: HypothesesIn) -> dict[str, Any]:
    det = body.model_dump()
    modo = det.pop("modo", "experimento")
    result = evaluate_detection(det, modo=modo)
    ecef = wgs84_to_ecef(STATION["lat_deg"], STATION["lon_deg"], STATION["h_m"])
    lora = pack_lora_uplink(result, ecef)
    ags = ags_core_supervisor_message(result, lora)
    result["ags_core"] = ags["ags_core"]
    result["lora_uplink"] = lora
    return result


@app.get("/api/v1/meteo")
def meteo(t: str = Query(default=""), force: bool = False) -> dict[str, Any]:
    out = meteo_mod.get_meteo(force=force)
    STATE.sources_last["meteo"] = {
        "fuente": out.get("fuente"),
        "http_status": out.get("http_status"),
        "fetched_at_madrid": out.get("fetched_at_madrid"),
    }
    out["t_query"] = t
    return out


@app.get("/api/v1/tle/pass")
def tle_pass(norad: int = 25544, t: str = Query(default=""), hours: float = 24.0, min_el_deg: float = 10.0) -> dict[str, Any]:
    out = tle_mod.predict_pass(norad=norad, hours=hours, min_el_deg=min_el_deg)
    STATE.sources_last["tle"] = {
        "fuente": out.get("tle_fuente"),
        "http_status": out.get("tle_http_status"),
        "fetched_at_madrid": out.get("fetched_at_madrid"),
        "norad": norad,
    }
    out["t_query"] = t
    return out


@app.get("/api/v1/adsb/crosscheck")
def adsb_crosscheck(
    t: str = Query(default=""),
    az: float = Query(default=0.0),
    el: float = Query(default=0.0),
    r: float = Query(default=50.0, description="radius NM"),
) -> dict[str, Any]:
    out = adsb_mod.crosscheck(t_iso=t or datetime.now(timezone.utc).isoformat(), az_deg=az, el_deg=el, radius_nm=r)
    STATE.sources_last["adsb"] = {
        "fuente": out.get("fuente"),
        "http_status": out.get("http_status"),
        "fetched_at_madrid": out.get("fetched_at_madrid"),
    }
    return out
