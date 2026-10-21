#!/usr/bin/env python3
"""Pruebas automatizadas reproducibles de componentes; no son calibración física."""
import json
import math
import os
import time
from core.ecef_bowring import ecef_to_lla, validar_ingreso_ecef
from core.triangulacion_enu import triangulacion_azel
from core.advanced_math_physics import ExtendedKalmanFilter3D, calcular_entropia_cinematica, verificar_crc16
from core.security import SecurityManager
from core.satellite_sensor_network import SatelliteSensorNetwork


def _run(name, fn):
    started = time.perf_counter()
    try:
        detail = fn()
        return {"nombre": name, "estado": "PASS", "duracion_ms": round((time.perf_counter()-started)*1000, 3), "detalles": str(detail)}
    except Exception as exc:
        return {"nombre": name, "estado": "FAIL", "duracion_ms": round((time.perf_counter()-started)*1000, 3), "detalles": f"{type(exc).__name__}: {exc}"}


def _test_wgs84():
    lat, lon, h = ecef_to_lla(6378137.0, 0.0, 0.0)
    assert abs(lat) < 1e-7 and abs(lon) < 1e-7 and abs(h) < 1e-3, (lat, lon, h)
    assert validar_ingreso_ecef(0, 0, 0)[0] is False
    # Punto geodésico conocido en Barcelona, transformado a ECEF con WGS84.
    phi, lam, height = math.radians(41.3278), math.radians(2.0947), 10.0
    e2 = 6.6943799901413165e-3
    n = 6378137.0 / math.sqrt(1.0 - e2 * math.sin(phi)**2)
    xyz = ((n+height)*math.cos(phi)*math.cos(lam), (n+height)*math.cos(phi)*math.sin(lam), (n*(1-e2)+height)*math.sin(phi))
    lat2, lon2, h2 = ecef_to_lla(*xyz)
    assert abs(lat2-41.3278) < 1e-8 and abs(lon2-2.0947) < 1e-8 and abs(h2-10.0) < 1e-3
    return f"ecuador y Barcelona WGS84 validados; Barcelona h={h2:.4f} m"


def _test_triangulation():
    # Blanco en ENU (1000, 2000, 500); azimut medido desde norte.
    target = (1000.0, 2000.0, 500.0)
    stations = [(0.0, 0.0, 0.0), (8000.0, 0.0, 0.0)]
    angles = []
    for x, y, z in stations:
        dx, dy, dz = target[0]-x, target[1]-y, target[2]-z
        az = math.degrees(math.atan2(dx, dy))
        el = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
        angles.append((az, el))
    ok, point, ta, tb, gap, msg = triangulacion_azel(stations[0], *angles[0], stations[1], *angles[1])
    assert ok and point is not None and gap < 1e-5, (ok, point, gap, msg)
    assert math.dist(point, target) < 1e-5, (point, target)
    return f"blanco recuperado; gap={gap:.3e} m"


def _test_entropy():
    h_const = calcular_entropia_cinematica([4.0]*20)
    h_var = calcular_entropia_cinematica([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert abs(h_const) < 1e-12 and h_var > 0
    return f"entropía constante={h_const:.3f} bit; variable={h_var:.3f} bit"


def _test_ekf():
    ekf = ExtendedKalmanFilter3D(dt=0.1)
    state, innovation = ekf.update([10, 20, 30])
    assert innovation == 0 and all(abs(float(state[i, 0])-v) < 1e-9 for i, v in enumerate([10,20,30]))
    state, innovation = ekf.update([10.2, 20, 30])
    assert np_is_finite(state) and np_is_finite(ekf.P) and innovation > 0
    assert max(abs(ekf.P-ekf.P.T).ravel()) < 1e-8
    return f"estado finito; innovación siguiente={innovation:.3f}"


def np_is_finite(value):
    import numpy as np
    return bool(np.all(np.isfinite(value)))


def _test_crc():
    assert verificar_crc16(b"123456789") == 0x29B1
    return "CRC-16/CCITT-FALSE vector estándar = 0x29B1"


def _test_security():
    manager = SecurityManager(config_path="/nonexistent/config.json")
    token = manager.generate_demo_token("clave_de_prueba_segura_123")
    assert manager.verify_token(token, "clave_de_prueba_segura_123")
    assert not manager.verify_token(token, "clave_incorrecta_456789")
    assert not manager.verify_token("Bearer inventado", "clave_de_prueba_segura_123")
    return "firma válida aceptada; clave incorrecta y token malformado rechazados"


def _test_satellite_simulation_label():
    result = SatelliteSensorNetwork().consultar_sensores_satelitales(41.0, 2.0, 1000.0)
    assert result["observaciones_reales"] is False
    assert result["estatus_validacion_satelital"] == "SIMULACION_NO_VALIDADA"
    return "el subsistema etiqueta explícitamente la telemetría como simulada"


def ejecutar_suite_calibracion_maestra():
    tests = [
        _run("Conversión WGS84 y rechazo de origen inválido", _test_wgs84),
        _run("Triangulación sintética ENU con blanco conocido", _test_triangulation),
        _run("Entropía de Shannon normalizada", _test_entropy),
        _run("EKF: inicialización, actualización y covarianza", _test_ekf),
        _run("CRC-16/CCITT-FALSE", _test_crc),
        _run("Autenticación HMAC con rechazo de token inválido", _test_security),
        _run("Etiquetado de telemetría simulada", _test_satellite_simulation_label),
    ]
    passed = sum(t["estado"] == "PASS" for t in tests)
    report = {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tipo": "pruebas_automatizadas_de_software_no_calibracion_fisica", "estatus_global": "PASS" if passed == len(tests) else "FAIL", "pruebas_pasadas": passed, "pruebas_totales": len(tests), "desglose": tests}
    print("=" * 76)
    print("NNC + AGs-Core — PRUEBAS AUTOMATIZADAS DE COMPONENTES")
    for i, test in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {test['estado']}: {test['nombre']} ({test['duracion_ms']} ms) — {test['detalles']}")
    print(f"RESULTADO: {passed}/{len(tests)} pruebas; {report['estatus_global']}")
    print("Nota: no equivale a calibración física, conexión satelital ni validación científica externa.")
    out_dir = os.path.join(os.path.dirname(__file__), "db")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "reporte_suite_calibracion.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report

if __name__ == "__main__":
    raise SystemExit(0 if ejecutar_suite_calibracion_maestra()["estatus_global"] == "PASS" else 1)
