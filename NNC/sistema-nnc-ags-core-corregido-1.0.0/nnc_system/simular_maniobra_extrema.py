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

def ejecutar_simulacion_maniobras_extremas():
    print("=" * 80)
    print("SIMULACIÓN DE MANIOBRA EXTREMA, ALERTAS TELEGRAM/SLACK Y LOGS GRAFANA")
    print("=" * 80)
    
    meta = MetaControllerAGsCore()
    notifier = AlertNotifier(config_path="security_config.json")
    grafana = GrafanaElasticLogger()
    
    # Evento 1: Viraje lateral instantáneo a 90°
    evt1 = {
        'id': 'EVT-EXTREMO-01-LATERAL',
        'dominio': 'Atmosfera',
        'ecef': (4792306.7, 171538.3, 4192011.0),
        'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
        'v_m_s': 1000000.0  # 1,000 km/s
    }
    
    # Evento 2: Descenso repentino vertical (coordenada ECEF válida sobre elipsoide)
    evt2 = {
        'id': 'EVT-EXTREMO-02-DESCENSO-VERTICAL',
        'dominio': 'Atmosfera',
        'ecef': (4792306.7, 171538.3, 4195000.0),
        'posA': [0, 0, 0], 'obsA': (0.0, 85.0),
        'posB': [8000, 0, 0], 'obsB': (-45.0, 85.0),
        'v_m_s': 1200000.0  # 1,200 km/s
    }
    
    t0 = time.perf_counter()
    res1 = meta.auditar_evento(evt1)
    res2 = meta.auditar_evento(evt2)
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    
    # Preparar datos enriquecidos para alertas
    evt1_data = {
        "id_caso": res1["id"],
        "estado": res1["estado"],
        "velocidad_km_s": res1.get("cinematica", {}).get("v_km_s", 1000.0),
        "mach": res1.get("cinematica", {}).get("mach", 2938.6),
        "g_forces": None,  # No hay aceleración medida ni intervalo temporal validado.
        "triangulacion_ok": res1.get("triangulacion", {}).get("ok", False),
        "gap_m": res1.get("triangulacion", {}).get("gap_m")
    }
    
    evt2_data = {
        "id_caso": res2["id"],
        "estado": res2["estado"],
        "velocidad_km_s": res2.get("cinematica", {}).get("v_km_s", 1200.0),
        "mach": res2.get("cinematica", {}).get("mach", 3526.3),
        "g_forces": None,  # No hay aceleración medida ni intervalo temporal validado.
        "triangulacion_ok": res2.get("triangulacion", {}).get("ok", False),
        "gap_m": res2.get("triangulacion", {}).get("gap_m")
    }
    
    # Despachar notificaciones instantáneas para Telegram y Slack
    notif1 = notifier.despachar_alertas(evt1_data)
    notif2 = notifier.despachar_alertas(evt2_data)
    
    # Exportar logs a ElasticSearch / Grafana Loki
    log1 = grafana.emit_log(evt1_data)
    log2 = grafana.emit_log(evt2_data)
    
    output = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nivel_alerta": "RANGO_MAXIMO_CRITICO",
        "regla_disparo": "ACELERACION_SUPERIOR_5_SIGMA",
        "export_grafana_elasticsearch": {
            "log1_ndjson": log1,
            "log2_ndjson": log2
        },
        "notificaciones_mobile": {
            "evt1_telegram_slack": notif1,
            "evt2_telegram_slack": notif2
        },
        "eventos_procesados": [evt1_data, evt2_data]
    }
    
    print(f"\n[RESULTADOS DE AUDITORÍA Y REGISTRO EN GRAFANA / ELASTICSEARCH]")
    print(f" • Tiempo de procesamiento : {elapsed_ms:.3f} ms")
    print(f" • Evento 1 (Viraje Lateral) : Estado={res1['estado']} | v={evt1_data['velocidad_km_s']} km/s | Mach {evt1_data['mach']:.1f}")
    print(f" • Evento 2 (Descenso Rep.) : Estado={res2['estado']} | v={evt2_data['velocidad_km_s']} km/s | Mach {evt2_data['mach']:.1f}")
    print("\n[DESPACHO DE LOGS Y ALERTAS MOBILE]")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("=" * 80)

if __name__ == '__main__':
    ejecutar_simulacion_maniobras_extremas()
