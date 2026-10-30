"""Station and threshold configuration for Ojo de Dios / NNC Consola v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# El Prat de Llobregat — approx town centre, NOT a surveyed station position.
STATION: dict[str, Any] = {
    "name": "El Prat de Llobregat (approx)",
    "lat_deg": 41.3275,
    "lon_deg": 2.0950,
    "h_m": 10.0,
    "coord_status": "PENDIENTE_DE_VERIFICACION",
    "coord_note": "Approximate town-centre WGS84; not a real surveyed NNC station.",
    "timezone": "Europe/Madrid",
}

HARDWARE: dict[str, Any] = {
    "camaras": 1,
    "camaras_duales": False,
    "baseline_m": None,
    "gnss": False,
    "gnss_pps": False,
    "ntp": False,
    "espectro": False,
    "polarimetria": False,
    "lora": False,
    "rtl_sdr_1090": False,
}

# Deterministic exclusion thresholds (initial; mark for calibration).
THRESHOLDS: dict[str, Any] = {
    "h1_sep_deg": 0.5,
    "h1_dt_s": 5.0,
    "h2_sep_deg": 0.3,
    "h2_dt_s": 3.0,
    "h3_sep_deg": 0.2,
    "h4_wind_tol": 0.20,  # ±20%
    "h6_max_duration_s": 3.0,
    "h_kin_accel_g": 50.0,
    "thresholds_status": "PENDIENTE_DE_VERIFICACION",
}

METEO_CACHE_S = 15 * 60
TLE_CACHE_S = 6 * 60 * 60
ADSB_CACHE_S = 30
USER_AGENT = "OjoDeDiosNNC/2.0 (ElPrat; research; local-dev)"

EVIDENCE_RULES = {
    "E0": "sin datos validos",
    "E1": "observacion unica no corroborada",
    "E2": "simulacion o modelo sin medida",
    "E3": "medida un sensor con tiempo sincronizado",
    "E4": "multisensor (2 camaras + GNSS/NTP)",
    "E5": "multisensor + fuente independiente",
    "E6": "replicada y revisada externamente",
}


@dataclass
class RuntimeState:
    """Mutable runtime flags recorded at boot / probe time."""

    modo: str = "experimento"  # or simulacion when forced
    sources_last: dict[str, Any] = field(default_factory=dict)
    live_probes: dict[str, Any] = field(default_factory=dict)


STATE = RuntimeState()
