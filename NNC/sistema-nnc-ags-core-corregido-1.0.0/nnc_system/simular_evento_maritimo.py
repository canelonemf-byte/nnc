#!/usr/bin/env python3
import time
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.ags_core_lora_agents import MetaControllerAGsCore
from core.notifier import AlertNotifier
from core.grafana_logger import GrafanaElasticLogger

def ejecutar_simulacion_maritima():
    print("=" * 80)
    print("SIMULACIÓN DE AUDITORÍA: ANOMALÍA TRANSMEDIA EN DOMINIO HIDROSFERA")
    print("=" * 80)
    
    meta = MetaControllerAGsCore()
    notifier = AlertNotifier(config_path=os.path.join(os.path.dirname(__file__), "security_config.json"))
    exporter = GrafanaElasticLogger()
    
    # Evento Marítimo en el Mar Mediterráneo (Costas de Barcelona / Prat de Llobregat)
    # Cota cero / Superficie marina: Altitud h = 0.5 m sobre elipsoide WGS84
    # Velocidad transmedia: 450 km/s (450,000 m/s) en agua/aire
    evt_maritimo = {
        'id': 'EVT-MAR-2026-MEDITERRANEO-01',
        'dominio': 'Hidrosfera',
        'ecef': (4795200.0, 175800.0, 4188500.0), # Coordenada ECEF marina válida sobre elipsoide WGS84
        'posA': [0, 0, 0], 'obsA': (45.0, 15.0), # Ángulo de observación marina sincronizada
        'posB': [8000, 0, 0], 'obsB': (-45.0, 15.0),
        'v_m_s': 450000.0 # 450 km/s
    }
    
    t0 = time.perf_counter()
    res = meta.auditar_evento(evt_maritimo)
    t1 = time.perf_counter()
    elapsed_ms = (t1 - t0) * 1000.0
    
    v_km_s = res.get("cinematica", {}).get("v_km_s", 450.0)
    v_m_s = v_km_s * 1000.0
    mach_hidro = v_m_s / 1480.0 # Mach acuático (velocidad del sonido en agua de mar ~1,480 m/s)
    mach_atmo = v_m_s / 340.3 # Mach atmosférico
    g_forces = None  # La velocidad por sí sola no determina la aceleración ni la carga g.
    
    evt_data = {
        "id_caso": res["id"],
        "dominio": res.get("dominio", "Hidrosfera"),
        "estado": res["estado"],
        "velocidad_km_s": v_km_s,
        "mach_acuatico": round(mach_hidro, 2),
        "mach_atmosferico": round(mach_atmo, 2),
        "fuerza_g": g_forces,
        "triangulacion_ok": res.get("triangulacion", {}).get("ok", False),
        "gap_m": res.get("triangulacion", {}).get("gap_m"),
        "refraccion_marina_deg": res.get("triangulacion", {}).get("refraccion_deg", 0.0),
        "entropia_shannon_bits": res.get("cinematica", {}).get("entropia_shannon", 0.0),
        "ekf_innovacion": res.get("cinematica", {}).get("ekf_innovacion", 0.0),
        "telemetria_crc16": res.get("telemetria", {}).get("crc16", "0x0")
    }
    
    notif_res = notifier.despachar_alertas(evt_data)
    log_ndjson = exporter.emit_log(evt_data)
    
    output = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nivel_alerta": "CRITICO_TRANSMEDIO_HIDROSFERA",
        "regla_disparo": "VELOCIDAD_SUPERIOR_ENVOLVENTE_HIDRODINAMICA",
        "tiempo_procesamiento_ms": round(elapsed_ms, 3),
        "datos_evento_maritimo": evt_data,
        "despacho_notificaciones_mobile": notif_res,
        "export_grafana_elasticsearch_ndjson": log_ndjson
    }
    
    print(f"\n[RESULTADOS DE AUDITORÍA Y NOTIFICACIONES EVENTO MARÍTIMO]")
    print(f" • Tiempo de procesamiento : {elapsed_ms:.3f} ms")
    print(f" • ID Caso                  : {evt_data['id_caso']}")
    print(f" • Dominio                  : {evt_data['dominio']}")
    print(f" • Estado                   : {evt_data['estado']}")
    print(f" • Velocidad                : {evt_data['velocidad_km_s']} km/s (450,000 m/s)")
    print(f" • Mach Acuático (1,480 m/s): Mach {evt_data['mach_acuatico']}")
    print(f" • Mach Atmosférico (340 m/s): Mach {evt_data['mach_atmosferico']}")
    print(" • Carga g                  : No calculable (sin aceleración medida)")
    print(f" • Refracción Marina        : {evt_data['refraccion_marina_deg']}°")
    print(f" • Entropía Cinemática     : {evt_data['entropia_shannon_bits']} bits")
    print(f" • Innovación EKF          : {evt_data['ekf_innovacion']}")
    print("\n[PAYLOAD COMPLETO DESPACHADO A TELEGRAM / SLACK / GRAFANA]")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("=" * 80)

if __name__ == '__main__':
    ejecutar_simulacion_maritima()
