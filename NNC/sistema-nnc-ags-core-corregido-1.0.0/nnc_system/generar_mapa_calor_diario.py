#!/usr/bin/env python3
"""
Generador de mapa de calor DEMOSTRATIVO a partir de escenarios sintéticos.
No procesa detecciones históricas verificadas ni demuestra maniobras físicamente imposibles.
"""

import json
import math
import time
import os

OUTPUT_JSON_PATH = os.path.join(os.path.dirname(__file__), "db", "mapa_calor_diario.json")

def generar_registro_mapa_calor():
    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    
    # Escenarios sintéticos para probar el renderizado; no son detecciones históricas verificadas.
    eventos_imposibles = [
        {
            "id": "EVT-MACH50-RIGHT-ANGLE-2026",
            "tipo": "MANIOBRA_ANGULO_RECTO_MACH50",
            "lat": 41.3879,
            "lon": 2.1699,
            "altitud_m": 12000.0,
            "velocidad_km_s": 17.015,
            "fuerza_g": None,  # Sin aceleración medida: carga g desconocida.
            "intensidad": 1.0,
            "timestamp_utc": "ESCENARIO_SINTETICO"
        },
        {
            "id": "EVT-INVERSION-VECTOR-180DEG",
            "tipo": "INVERSION_VECTORIAL_INSTANTANEA",
            "lat": 40.4168,
            "lon": -3.7038,
            "altitud_m": 8500.0,
            "velocidad_km_s": 1000.0,
            "fuerza_g": None,  # Sin aceleración medida: carga g desconocida.
            "intensidad": 0.95,
            "timestamp_utc": "ESCENARIO_SINTETICO"
        },
        {
            "id": "EVT-TRANSMEDIO-MEDITERRANEO-2026",
            "tipo": "TRANSICION_TRANSMEDIO_SIN_DESACELERACION",
            "lat": 38.5021,
            "lon": 3.2045,
            "altitud_m": -150.0,
            "velocidad_km_s": 1500.0,
            "fuerza_g": None,  # Sin aceleración medida: carga g desconocida.
            "intensidad": 0.98,
            "timestamp_utc": "ESCENARIO_SINTETICO"
        },
        {
            "id": "EVT-ENJAMBRE-HOTSPOT-PRAT",
            "tipo": "TRACKING_ENJAMBRE_HIPERVELOCIDAD",
            "lat": 41.3128,
            "lon": 2.1023,
            "altitud_m": 420000.0,
            "velocidad_km_s": 1200.0,
            "fuerza_g": None,  # Sin aceleración medida: carga g desconocida.
            "intensidad": 0.92,
            "timestamp_utc": "ESCENARIO_SINTETICO"
        },
        {
            "id": "EVT-EXOSFERA-LEO-ACCELERATION",
            "tipo": "ACELERACION_EXOSFERICA_DESCONOCIDA",
            "lat": 36.7213,
            "lon": -4.4214,
            "altitud_m": 350000.0,
            "velocidad_km_s": 2200.0,
            "fuerza_g": None,  # Sin aceleración medida: carga g desconocida.
            "intensidad": 0.88,
            "timestamp_utc": "ESCENARIO_SINTETICO"
        }
    ]
    
    # Generar puntos de densidad estocásticos alrededor de los puntos calientes
    puntos_mapa_calor = []
    for evt in eventos_imposibles:
        puntos_mapa_calor.append({
            "lat": evt["lat"],
            "lon": evt["lon"],
            "altitud_m": evt["altitud_m"],
            "peso": evt["intensidad"],
            "id": evt["id"],
            "tipo": evt["tipo"]
        })
        # Agregar micro-cluster alrededor del hotspot
        for i in range(5):
            dlat = (math.sin(i * 1.2) * 0.08)
            dlon = (math.cos(i * 1.2) * 0.08)
            puntos_mapa_calor.append({
                "lat": round(evt["lat"] + dlat, 4),
                "lon": round(evt["lon"] + dlon, 4),
                "altitud_m": evt["altitud_m"],
                "peso": round(evt["intensidad"] * 0.6, 2),
                "id": f"{evt['id']}-cluster-{i}",
                "tipo": evt["tipo"]
            })

    heatmap_payload = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tipo_datos": "SINTETICOS_DEMO_NO_OBSERVACIONES_REALES",
        "validacion_fisica": False,
        "total_hotspots": len(eventos_imposibles),
        "total_puntos_densidad": len(puntos_mapa_calor),
        "rango_fechas": "2026-10-19 / 2026-10-20 (Últimas 24h)",
        "criterio_filtro": "ESCENARIOS_DEMO_NO_CLASIFICACION_VALIDADA",
        "puntos_mapa_calor": puntos_mapa_calor
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(heatmap_payload, f, indent=2, ensure_ascii=False)

    print(f"[Mapa de Calor] Registro diario generado exitosamente en: {OUTPUT_JSON_PATH}")
    return heatmap_payload

if __name__ == "__main__":
    generar_registro_mapa_calor()
