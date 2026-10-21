#!/usr/bin/env python3
import time
import json
import os
import sys

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.ags_core_lora_agents import MetaControllerAGsCore
from core.notifier import AlertNotifier
from core.grafana_logger import GrafanaElasticLogger

def ejecutar_simulacion_espacial():
    print("=" * 80)
    print("SIMULACIÓN DE AUDITORÍA: TRAZAS ORBITALES Y EXOSFERA (DOMINIO ESPACIO)")
    print("=" * 80)
    
    meta = MetaControllerAGsCore()
    notifier = AlertNotifier(config_path="security_config.json")
    exporter = GrafanaElasticLogger()
    
    # Evento 1: Pasada de la Estación Espacial Internacional (ISS - NORAD #25544)
    evt_iss = {
        'id': 'EVT-ESPACIO-2026-ISS-01',
        'dominio': 'Exosfera',
        'altitud_m': 420000.0,
        'ecef': (4792306.7, 171538.3, 4612011.0),
        'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
        'v_m_s': 7660.0,  # 7.66 km/s (Velocidad orbital LEO)
        'tle_match': 'ISS (ZARYA) NORAD #25544 [Coincidencia angular < 0.01°]'
    }
    
    # Evento 2: Objeto no correlacionado hiperveloz en órbita LEO
    evt_anomalia = {
        'id': 'EVT-ESPACIO-2026-ANOMALIA-02',
        'dominio': 'Exosfera',
        'altitud_m': 420000.0,
        'ecef': (4792306.7, 171538.3, 4612011.0),
        'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
        'v_m_s': 1500000.0,  # 1,500 km/s (Hipervelocidad exótica)
        'tle_match': None
    }
    
    t0 = time.perf_counter()
    res1 = meta.auditar_evento(evt_iss)
    res2 = meta.auditar_evento(evt_anomalia)
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    
    # Formatear datos para exportadores
    evt1_data = {
        "id_caso": res1["id"],
        "dominio": res1["dominio"],
        "estado": res1["estado"],
        "filtro_h3": res1["filtro_h3_tle"],
        "altitud_km": res1["cinematica"]["altitud_km"],
        "velocidad_km_s": res1["cinematica"]["v_km_s"],
        "mach": res1["cinematica"]["mach"],
        "triangulacion_ok": res1["triangulacion"]["ok"],
        "gap_m": res1["triangulacion"]["gap_m"],
        "entropia_shannon_bits": res1["cinematica"]["entropia_shannon"],
        "ekf_innovacion": res1["cinematica"]["ekf_innovacion"],
        "telemetria_crc16": res1["telemetria"]["crc16"]
    }
    
    evt2_data = {
        "id_caso": res2["id"],
        "dominio": res2["dominio"],
        "estado": res2["estado"],
        "filtro_h3": res2["filtro_h3_tle"],
        "altitud_km": res2["cinematica"]["altitud_km"],
        "velocidad_km_s": res2["cinematica"]["v_km_s"],
        "mach": res2["cinematica"]["mach"],
        "g_forces": None,  # No hay aceleración medida ni intervalo temporal validado.
        "triangulacion_ok": res2["triangulacion"]["ok"],
        "gap_m": res2["triangulacion"]["gap_m"],
        "entropia_shannon_bits": res2["cinematica"]["entropia_shannon"],
        "ekf_innovacion": res2["cinematica"]["ekf_innovacion"],
        "telemetria_crc16": res2["telemetria"]["crc16"]
    }
    
    # Despachar notificaciones e inyección a Grafana
    notif_mobile = notifier.despachar_alertas(evt2_data)
    log_ndjson = exporter.emit_log(evt2_data)
    
    summary = {
        "timestamp_utc": "2026-10-20T01:31:00Z",
        "nivel_alerta": "CRITICO_EXOSFERA_UNTRACKED",
        "regla_disparo": "VELOCIDAD_HIPERBOLICA_SIN_TLE_NORAD",
        "tiempo_procesamiento_ms": round(elapsed_ms, 3),
        "evento_satelite_conocido": evt1_data,
        "evento_anomalia_exosfera": evt2_data,
        "despacho_alertas_mobile": notif_mobile,
        "export_grafana_ndjson": log_ndjson
    }
    
    print(f"\n[RESULTADOS DE AUDITORÍA ORBITAL Y NOTIFICACIONES]")
    print(f" • Tiempo de procesamiento : {elapsed_ms:.3f} ms")
    print(f" • Evento 1 (Pase ISS)       : Estado={res1['estado']} | Filtro H3={res1['filtro_h3_tle']}")
    print(f" • Evento 2 (Traza Anómala) : Estado={res2['estado']} | v={res2['cinematica']['v_km_s']} km/s | Filtro H3={res2['filtro_h3_tle']}")
    print("\n[PAYLOAD DE AUDITORÍA DE EXOSFERA DESPACHADO]")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("=" * 80)

if __name__ == '__main__':
    ejecutar_simulacion_espacial()
