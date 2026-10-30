import math

from ojo_de_dios.math_geo import (
    angular_sep_azel_deg,
    haversine_km,
    sha256_canonical,
    wgs84_to_ecef,
)


def test_wgs84_ecef_equator():
    # φ=0, λ=0, h=0 → X≈a, Y≈0, Z≈0
    e = wgs84_to_ecef(0.0, 0.0, 0.0)
    assert abs(e["x_m"] - 6378137.0) < 1e-6
    assert abs(e["y_m"]) < 1e-6
    assert abs(e["z_m"]) < 1e-6


def test_wgs84_ecef_north_pole():
    e = wgs84_to_ecef(90.0, 0.0, 0.0)
    b = 6378137.0 * (1 - 1 / 298.257223563)  # approx semi-minor
    assert abs(e["x_m"]) < 1e-6
    assert abs(e["y_m"]) < 1e-6
    assert abs(e["z_m"] - b) < 1.0  # within 1 m


def test_angular_sep_identical():
    assert angular_sep_azel_deg(10, 20, 10, 20) < 1e-9


def test_angular_sep_orthogonalish():
    # az differ 90 at el=0 → 90 deg
    sep = angular_sep_azel_deg(0, 0, 90, 0)
    assert abs(sep - 90.0) < 1e-6


def test_haversine_zero():
    assert haversine_km(41.3, 2.1, 41.3, 2.1) == 0.0


def test_sha256_stable():
    a = sha256_canonical({"b": 1, "a": 2})
    b = sha256_canonical({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64
