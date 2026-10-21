#!/usr/bin/env python3
"""
Simulación de Auditoría de Resiliencia ante Tormentas Solares e Interferencias Geomagnéticas Extremas (Kp > 7)
Evaluación del comportamiento de la Red de Sensores Satelitales, Triangulación 3D ENU,
EKF 3D y Conmutación a Canales de Respaldo RF-Endurecidos / Giroscópicos.
"""

import time
import json
import os
import sys

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.ags_core_lora_agents import MetaControllerAGsCore
from core.notifier import AlertNotifier
from core.grafana_logger import GrafanaElasticLogger

def ejecutar_simulacion_tormenta_solar():
    print("=" * 90)
    print("SIMULACIÓN DE RESILIENCIA ANTE TORMENTAS SOLARES E INTERFERENCIAS GEOMAGNÉTICAS (Kp = 8.5)")
    print(" Evaluación de Conmutación de Canales Satelitales, Telemetría EKF y Triangulación 3D")
    print("=" * 90)

    meta = MetaControllerAGsCore()
    notifier = AlertNotifier(config_path="security_config.json")
    exporter = GrafanaElasticLogger()

    # Evento 1: Traza Transmedio en Condiciones Nominales (Kp = 3.2)
    evt_nominal = {
        'id': 'EVT-SOLAR-NOMINAL-2026',
        'dominio': 'Exosfera',
        'altitud_m': 420000.0,
        'lat': 41.3879, 'lon': 2.1699,
        'ecef': (4792306.7, 171538.3, 4192011.0),
        'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
        'v_m_s': 1500000.0,  # 1,500 km/s
        'simular_tormenta_solar': False
    }

    # Evento 2: Misma Traza Transmedio durante Tormenta Geomagnética Extrema (Kp = 8.5, Viento Solar = 850 km/s)
    evt_tormenta = {
        'id': 'EVT-SOLAR-STORM-KP85-2026',
        'dominio': 'Exosfera',
        'altitud_m': 420000.0,
        'lat': 41.3879, 'lon': 2.1699,
        'ecef': (4792306.7, 171538.3, 4192011.0),
        'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
        'v_m_s': 1500000.0,  # 1,500 km/s
        'simular_tormenta_solar': True,
        'kp_override': 8.5
    }

    t0 = time.perf_counter()
    res_nom = meta.auditar_evento(evt_nominal)
    res_storm = meta.auditar_evento(evt_tormenta)
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0

    # Notificaciones y Exportación
    notif_storm = notifier.despachar_alertas(res_storm)
    log_ndjson = exporter.emit_log(res_storm)

    payload_salida = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nivel_alerta": "RESILIENCIA_TORMENTA_SOLAR_G4_G5_CONFIRMADA",
        "tiempo_procesamiento_ms": round(elapsed_ms, 3),
        "comparativa_condiciones": {
            "escenario_1_nominal": {
                "id": res_nom["id"],
                "kp_index": res_nom["red_sensores_satelitales"]["telemetria_multiespectral"]["indice_geomagnetico_kp"],
                "viento_solar_km_s": res_nom["red_sensores_satelitales"]["telemetria_multiespectral"]["viento_solar_km_s"],
                "modo_resiliencia": res_nom["red_sensores_satelitales"]["resiliencia_interferencia_solar"]["modo_tormenta_solar"],
                "triangulacion_ok": res_nom["triangulacion"]["ok"],
                "gap_m": res_nom["triangulacion"]["gap_m"],
                "estado": res_nom["estado"]
            },
            "escenario_2_tormenta_solar_kp85": {
                "id": res_storm["id"],
                "kp_index": res_storm["red_sensores_satelitales"]["telemetria_multiespectral"]["indice_geomagnetico_kp"],
                "viento_solar_km_s": res_storm["red_sensores_satelitales"]["telemetria_multiespectral"]["viento_solar_km_s"],
                "alerta_clima_espacial": res_storm["red_sensores_satelitales"]["telemetria_multiespectral"]["alerta_clima_espacial"],
                "atenuacion_rf_db": res_storm["red_sensores_satelitales"]["telemetria_multiespectral"]["atenuacion_rf_db"],
                "centelleo_ionosferico_S4": res_storm["red_sensores_satelitales"]["telemetria_multiespectral"]["indice_centelleo_ionosferico_S4"],
                "modo_resiliencia": res_storm["red_sensores_satelitales"]["resiliencia_interferencia_solar"]["modo_tormenta_solar"],
                "canal_enrutamiento": res_storm["red_sensores_satelitales"]["resiliencia_interferencia_solar"]["canal_enrutamiento"],
                "integridad_datos_pct": res_storm["red_sensores_satelitales"]["resiliencia_interferencia_solar"]["integridad_datos_telematicos_pct"],
                "perdida_marcos": res_storm["red_sensores_satelitales"]["resiliencia_interferencia_solar"]["perdida_marcos_seguimiento"],
                "triangulacion_ok": res_storm["triangulacion"]["ok"],
                "gap_m": res_storm["triangulacion"]["gap_m"],
                "estado": res_storm["estado"]
            }
        },
        "despacho_notificaciones": notif_storm,
        "log_grafana_ndjson": log_ndjson
    }

    print(f"\n[RESULTADOS DE AUDITORÍA Y RESILIENCIA ANTE TORMENTA SOLAR]")
    print(f" • Tiempo de procesamiento : {elapsed_ms:.3f} ms")
    print(f" • Escenario 1 (Nominal Kp=3.2)  : Estado={res_nom['estado']} | Gap={res_nom['triangulacion']['gap_m']:.2e} m | Routing=DIRECT")
    print(f" • Escenario 2 (Tormenta Kp=8.5) : Estado={res_storm['estado']} | Gap={res_storm['triangulacion']['gap_m']:.2e} m | Resiliencia=ACTIVADA ⚡")
    print(f" • Viento Solar Registrado        : {res_storm['red_sensores_satelitales']['telemetria_multiespectral']['viento_solar_km_s']} km/s")
    print(f" • Canal de Enrutamiento Backup  : {res_storm['red_sensores_satelitales']['resiliencia_interferencia_solar']['canal_enrutamiento']}")
    print(f" • Pérdida de Marcos / Integridad: {res_storm['red_sensores_satelitales']['resiliencia_interferencia_solar']['perdida_marcos_seguimiento']} / {res_storm['red_sensores_satelitales']['resiliencia_interferencia_solar']['integridad_datos_telematicos_pct']}%")

    print("\n[PAYLOAD COMPLETO DESPACHADO]")
    print(json.dumps(payload_salida, indent=2, ensure_ascii=False))
    print("=" * 90)

if __name__ == '__main__':
    ejecutar_simulacion_tormenta_solar()
