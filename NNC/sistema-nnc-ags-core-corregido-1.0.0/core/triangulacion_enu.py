"""Triangulación por dos líneas de visión en un marco cartesiano ENU común.

Las posiciones deben expresarse en metros y en el mismo marco local ENU.
Azimut: grados desde el norte, sentido horario; elevación: grados sobre horizonte.
"""
import math
import numpy as np

def dir_vector_enu(az_deg, el_deg):
    az, el = float(az_deg), float(el_deg)
    if not math.isfinite(az) or not math.isfinite(el) or not -90.0 <= el <= 90.0:
        raise ValueError("Azimut/elevación no válidos")
    az_rad, el_rad = math.radians(az), math.radians(el)
    return np.array([math.sin(az_rad)*math.cos(el_rad), math.cos(az_rad)*math.cos(el_rad), math.sin(el_rad)], dtype=float)

def triangulacion_azel(posA, azA, elA, posB, azB, elB):
    try:
        pA, pB = np.asarray(posA, dtype=float), np.asarray(posB, dtype=float)
        if pA.shape != (3,) or pB.shape != (3,) or not np.all(np.isfinite(pA)) or not np.all(np.isfinite(pB)):
            raise ValueError("Las posiciones deben ser vectores ENU finitos de tres componentes")
        dA, dB = dir_vector_enu(azA, elA), dir_vector_enu(azB, elB)
    except (TypeError, ValueError, OverflowError):
        return False, None, 0.0, 0.0, None, "Entrada_invalida"
    dp = pB - pA
    dot = float(np.dot(dA, dB))
    denom = 1.0 - dot * dot
    if denom < 1e-10:
        return False, None, 0.0, 0.0, None, "Rayos_paralelos_o_mal_condicionados"
    # Solución de mínimos cuadrados para puntos más cercanos en dos rayos.
    rhs = np.array([np.dot(dA, dp), -np.dot(dB, dp)], dtype=float)
    M = np.array([[1.0, -dot], [-dot, 1.0]], dtype=float)
    tA, tB = np.linalg.solve(M, rhs)
    if tA <= 0 or tB <= 0:
        return False, None, float(tA), float(tB), None, "Interseccion_detras_de_sensor"
    qA, qB = pA + tA*dA, pB + tB*dB
    gap = float(np.linalg.norm(qA-qB))
    return True, (qA+qB)/2.0, float(tA), float(tB), gap, "OK"
