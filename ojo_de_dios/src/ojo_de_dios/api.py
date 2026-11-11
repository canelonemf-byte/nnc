"""FastAPI REST surface for Ojo de Dios / NNC Consola v2."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    lat_deg: float = Field(ge=-90, le=90)
    lon_deg: float = Field(ge=-180, le=180)
    h_m: float = Field(default=0.0, ge=-500, le=1.0e6, description="altura ELIPSOIDAL WGS84 (m)")
    t: str = ""
    id: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class HypothesesIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    id: str = Field(default="", max_length=128)
    t: str = Field(default="", max_length=64)
    az_deg: float = Field(ge=0, lt=360)
    el_deg: float = Field(ge=-90, le=90)
    duration_s: Optional[float] = Field(default=None, ge=0, le=86400)
    frames: int = Field(default=0, ge=0, le=10_000_000)
    camaras_coincidentes: int = Field(default=0, ge=0, le=16)
    distance_m: Optional[float] = Field(default=None, gt=0)
    distance_err_m: Optional[float] = Field(default=None, ge=0)
    accel_err_g: Optional[float] = Field(default=None, ge=0)
    fuente_independiente: bool = False
    revision_externa: bool = False
    single_frame: bool = False
    artefacto_sensor: bool = False
    callsign_hint: str = ""
    norad_hint: Optional[int] = None
    force_h1: bool = False
    force_h2: bool = False
    adsb_aircraft: Optional[dict[str, Any]] = None
    wind_drift_error_pct: Optional[float] = None
    parallax_high: Optional[bool] = None
    size_angular_incoherent: bool = False
    trajectory_linear: Optional[bool] = None
    optical_geometry_coherent: Optional[bool] = None
    accel_g: Optional[float] = None
    spectral_anomaly: Optional[bool] = None
    modo: str = "experimento"
    origen: str = ""
    t_sync: bool = False


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
    try:
        result = evaluate_detection(det, modo=modo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ecef = wgs84_to_ecef(STATION["lat_deg"], STATION["lon_deg"], STATION["h_ell_m"])
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
def tle_pass(norad: int = Query(default=25544, ge=1, le=999999), t: str = Query(default=""), hours: float = Query(default=24.0, gt=0, le=72), min_el_deg: float = Query(default=10.0, ge=0, le=89), sun_alt_max_deg: float = Query(default=-6.0, ge=-18, le=0)) -> dict[str, Any]:
    out = tle_mod.predict_pass(norad=norad, hours=hours, min_el_deg=min_el_deg, sun_alt_max_deg=sun_alt_max_deg)
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
    az: float = Query(default=0.0, ge=0, lt=360),
    el: float = Query(default=0.0, ge=-90, le=90),
    r: float = Query(default=50.0, gt=0, le=250, description="radius NM"),
) -> dict[str, Any]:
    out = adsb_mod.crosscheck(t_iso=t or datetime.now(timezone.utc).isoformat(), az_deg=az, el_deg=el, radius_nm=r)
    STATE.sources_last["adsb"] = {
        "fuente": out.get("fuente"),
        "http_status": out.get("http_status"),
        "fetched_at_madrid": out.get("fetched_at_madrid"),
    }
    return out
