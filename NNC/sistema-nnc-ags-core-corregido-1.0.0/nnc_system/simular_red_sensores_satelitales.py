#!/usr/bin/env python3
"""
Script de Prueba y Verificación Automatizada:
Red Integrada de Sensores Satelitales en Tiempo Real (NNC + AGs-Core)
"""

import time
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.ags_core_lora_agents import MetaControllerAGsCore
from core.satellite_sensor_network import SatelliteSensorNetwork
from core.notifier import AlertNotifier
from core.grafana_logger import GrafanaElasticLogger

def ejecutar_prueba_sensores_satelitales():
    print("=" * 90)
    print("SISTEMA NNC + AGs-CORE: SIMULACIÓN DE SENSORES SATELITALES (SIN CONEXIONES REALES)")
    print("=" * 90)
    
    meta = MetaControllerAGsCore()
    sat_net = SatelliteSensorNetwork()
    notifier = AlertNotifier(config_path="security_config.json")
    logger = GrafanaElasticLogger()
    
    # Evento de Prueba con Sensores Satelitales Multiespectrales
    evt_sat = {
        'id': 'EVT-SAT-SENSOR-REALTIME-2026',
        'dominio': 'Exosfera',
        'altitud_m': 420000.0,
        'lat': 41.3879,
        'lon': 2.1699,
        'ecef': (4792306.7, 171538.3, 4192011.0),
        'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
        'v_m_s': 1500000.0  # 1,500 km/s
    }
    
    t0 = time.perf_counter()
    resultado = meta.auditar_evento(evt_sat)
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    
    # Preparación de datos para notificación
    evt_data = {
        "id_caso": resultado["id"],
        "estado": resultado["estado"],
        "velocidad_km_s": resultado["cinematica"]["v_km_s"],
        "mach": resultado["cinematica"]["mach"],
        "g_forces": None,  # No hay aceleración medida ni intervalo temporal validado.
        "triangulacion_ok": resultado["triangulacion"]["ok"],
        "gap_m": resultado["triangulacion"]["gap_m"]
    }
    
    notif = notifier.despachar_alertas(evt_data)
    log_entry = logger.emit_log(evt_data)
    
    output = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "estatus_integracion": "SIMULACION_SENSORES_NO_CONECTADOS",
        "tiempo_procesamiento_ms": elapsed_ms,
        "constelaciones_monitoreadas": list(sat_net.constelaciones_activas.keys()),
        "resultado_auditoria": resultado,
        "notificaciones_mobile": notif,
        "log_grafana_ndjson": log_entry
    }
    
    print("\n[RESULTADOS DE AUDITORÍA Y CRUCE DE SENSORES SATELITALES]")
    print(f" • Tiempo de procesamiento : {elapsed_ms:.3f} ms")
    print(f" • ID Caso                  : {resultado['id']}")
    print(f" • Estado                   : {resultado['estado']}")
    print(f" • Catálogo ilustrativo      : {len(sat_net.constelaciones_activas)} Redes Satelitales")
    print(f" • Sensores reales en cobertura: {resultado['red_sensores_satelitales']['sensores_satelitales_en_cobertura']} Satélites Streaming")
    print(f" • Telemetría SAR Radar     : {resultado['red_sensores_satelitales']['telemetria_multiespectral']['radar_sar_backscatter_db']} dB")
    print(f" • Anomalía Térmica IR     : {resultado['red_sensores_satelitales']['telemetria_multiespectral']['anomalia_termica_ir_kelvin']} K")
    print(f" • Viento Solar / Mag. L1  : {resultado['red_sensores_satelitales']['telemetria_multiespectral']['viento_solar_km_s']} km/s (Kp={resultado['red_sensores_satelitales']['telemetria_multiespectral']['indice_geomagnetico_kp']})")
    
    print("\n[PAYLOAD COMPLETO SIMULACIÓN DE SENSORES SATELITALES]")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("=" * 90)

if __name__ == '__main__':
    ejecutar_prueba_sensores_satelitales()
