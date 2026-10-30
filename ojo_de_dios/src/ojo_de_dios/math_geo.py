"""
Geodetic and angular mathematics for Ojo de Dios.

WGS84 constants (NIMA TR8350.2):
  a = 6378137.0 m
  f = 1/298.257223563
  e^2 = f(2-f)

Geodetic (φ, λ, h) → ECEF:
  N(φ) = a / sqrt(1 - e² sin²φ)
  X = (N + h) cosφ cosλ
  Y = (N + h) cosφ sinλ
  Z = (N(1 - e²) + h) sinφ

Angular separation on the unit sphere for az/el:
  Convert (az, el) → unit vector:
    x = cos(el) sin(az)
    y = cos(el) cos(az)
    z = sin(el)
  θ = acos(clip(u·v, -1, 1))
  Equivalent haversine form on (az, el) treated as (lon, lat):
    hav(θ) = hav(Δel) + cos(el1)cos(el2)hav(Δaz)
    θ = 2 asin(sqrt(hav))
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


def wgs84_to_ecef(lat_deg: float, lon_deg: float, h_m: float) -> dict[str, float]:
    """Convert WGS84 geodetic coordinates to ECEF metres."""
    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi * sin_phi)
    x = (n + h_m) * cos_phi * math.cos(lam)
    y = (n + h_m) * cos_phi * math.sin(lam)
    z = (n * (1.0 - WGS84_E2) + h_m) * sin_phi
    return {"x_m": x, "y_m": y, "z_m": z, "n_m": n}


def ecef_distance_m(a: dict[str, float], b: dict[str, float]) -> float:
    dx = a["x_m"] - b["x_m"]
    dy = a["y_m"] - b["y_m"]
    dz = a["z_m"] - b["z_m"]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def angular_sep_azel_deg(az1_deg: float, el1_deg: float, az2_deg: float, el2_deg: float) -> float:
    """
    Great-circle angular separation between two az/el directions (degrees).
    Uses haversine with elevation as latitude and azimuth as longitude.
    """
    el1 = math.radians(el1_deg)
    el2 = math.radians(el2_deg)
    daz = math.radians(az2_deg - az1_deg)
    # wrap Δaz into [-π, π] for numerical stability
    daz = (daz + math.pi) % (2 * math.pi) - math.pi
    hav_el = math.sin((el2 - el1) / 2.0) ** 2
    hav_az = math.sin(daz / 2.0) ** 2
    h = hav_el + math.cos(el1) * math.cos(el2) * hav_az
    h = min(1.0, max(0.0, h))
    return math.degrees(2.0 * math.asin(math.sqrt(h)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Forward azimuth from point 1 to point 2 (degrees, 0=N)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlam / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def elevation_from_range_alt_deg(dist_m: float, alt_m: float) -> float:
    """Approximate elevation looking from station to target at height alt_m, ground range dist_m."""
    if dist_m <= 0:
        return 90.0 if alt_m > 0 else 0.0
    return math.degrees(math.atan2(alt_m, dist_m))


def sha256_canonical(obj: Any) -> str:
    """SHA-256 of canonical JSON (sorted keys, no spaces)."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def equations_doc() -> dict[str, str]:
    return {
        "wgs84_to_ecef": (
            "N=a/sqrt(1-e2*sin^2(phi)); "
            "X=(N+h)cos(phi)cos(lam); Y=(N+h)cos(phi)sin(lam); "
            "Z=(N(1-e2)+h)sin(phi); a=6378137; f=1/298.257223563; e2=f(2-f)"
        ),
        "angular_sep_azel": (
            "hav(theta)=hav(Delta_el)+cos(el1)cos(el2)hav(Delta_az); "
            "theta=2*asin(sqrt(hav)); az~lon, el~lat on unit sphere"
        ),
        "backoff_429": (
            "delay_s = min(2^attempt, 16) or Retry-After if present; "
            "attempts={0,1,2,3}; cache_ttl_meteo=900s"
        ),
        "sgp4": "SGP4/SDP4 via skyfield EarthSatellite from Celestrak GP/TLE (NORAD)",
        "evidence_cap": (
            "without dual cameras+GNSS/NTP: max E3; "
            "without measured H_kin: no anomaly claim beyond no_identificado_insuficiente"
        ),
    }
