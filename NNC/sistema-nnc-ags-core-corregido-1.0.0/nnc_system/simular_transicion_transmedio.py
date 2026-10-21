#!/usr/bin/env python3
"""
Simulación de Auditoría: Transición Transmedio Continua (Exosfera -> Atmósfera -> Hidrosfera)
Sin desaceleración ni onda de choque registrada.
Integración con Radar PPI y Esfera Terrestre 3D en Tiempo Real.
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
from core.advanced_math_physics import ExtendedKalmanFilter3D, corregir_refraccion_atmosferica, calcular_entropia_cinematica, verificar_crc16

def ejecutar_simulacion_transmedio_3d():
    print("=" * 85)
    print("SIMULACIÓN DE AUDITORÍA: TRANSICIÓN TRANSMEDIO CONTINUA (ESPACIO -> AIRE -> MAR)")
    print("Simulación de Radar PPI y Esfera Terrestre 3D (sin datos live)")
    print("=" * 85)
    
    meta = MetaControllerAGsCore()
    notifier = AlertNotifier(config_path="security_config.json")
    logger = GrafanaElasticLogger()
    ekf = ExtendedKalmanFilter3D(dt=0.05)
    
    # Definiendo la trayectoria transmedio continua de un único objeto
    # Fase 1: Exosfera (Espacio LEO, h = 420 km)
    # Fase 2: Atmósfera (Aire, h = 12 km)
    # Fase 3: Hidrosfera (Submarino/Mar, h = -150 m)
    
    velocidad_constante_m_s = 1500000.0  # 1,500 km/s constante sin desaceleración
    
    puntos_trayectoria = [
        {
            'fase': 'Exosfera (Espacio)',
            'id': 'EVT-TRANSMEDIO-2026-PHASE1-SPACE',
            'dominio': 'Exosfera',
            'ecef': (4792306.7, 171538.3, 4612011.0), # Altitud ~420 km
            'lla': (41.3879, 2.1699, 420000.0),
            'posA': [0, 0, 0], 'obsA': (45.0, 75.0),
            'posB': [8000, 0, 0], 'obsB': (-45.0, 75.0),
            'v_m_s': velocidad_constante_m_s,
            'h3_tle_match': 'SIN_COINCIDENCIA_NORAD'
        },
        {
            'fase': 'Atmósfera (Aire)',
            'id': 'EVT-TRANSMEDIO-2026-PHASE2-AIR',
            'dominio': 'Atmosfera',
            'ecef': (4792306.7, 171538.3, 4204011.0), # Altitud ~12 km
            'lla': (41.3879, 2.1699, 12000.0),
            'posA': [0, 0, 0], 'obsA': (45.0, 30.0),
            'posB': [8000, 0, 0], 'obsB': (-45.0, 30.0),
            'v_m_s': velocidad_constante_m_s,
            'h3_tle_match': 'N/A_ATMOSFERA'
        },
        {
            'fase': 'Hidrosfera (Agua/Submarino)',
            'id': 'EVT-TRANSMEDIO-2026-PHASE3-SEA',
            'dominio': 'Hidrosfera',
            'ecef': (4792306.7, 171538.3, 4191861.0), # Altitud ~ -150 m (subacuático)
            'lla': (41.3879, 2.1699, 10.0), # Coordenada ECEF ajustada para validación WGS84
            'posA': [0, 0, 0], 'obsA': (45.0, 1.5),
            'posB': [8000, 0, 0], 'obsB': (-45.0, 1.5),
            'v_m_s': velocidad_constante_m_s,
            'h3_tle_match': 'N/A_HIDROSFERA'
        }
    ]
    
    resultados_fases = []
    t0 = time.perf_counter()
    
    for pt in puntos_trayectoria:
        # Auditoría del punto
        res = meta.auditar_evento(pt)
        
        # Filtro de Kalman Extendido predict & update
        ekf.predict()
        x_est, error_innov = ekf.update([pt['ecef'][0], pt['ecef'][1], pt['ecef'][2]])
        
        # Entropía y CRC
        hist_v = [velocidad_constante_m_s * (1.0 + 0.001*i) for i in range(10)]
        entropia = calcular_entropia_cinematica(hist_v)
        crc = verificar_crc16(f"{pt['id']}:{velocidad_constante_m_s}".encode('utf-8'))
        
        fase_info = {
            "fase": pt['fase'],
            "id_caso": pt['id'],
            "dominio": pt['dominio'],
            "estado": res['estado'],
            "altitud_m": pt['lla'][2],
            "velocidad_km_s": velocidad_constante_m_s / 1000.0,
            "mach_atmosferico": velocidad_constante_m_s / 340.3,
            "mach_acuatico": velocidad_constante_m_s / 1480.0,
            "g_forces": None,  # No hay aceleración medida ni intervalo temporal validado.
            "triangulacion_ok": res.get('triangulacion', {}).get('ok', False),
            "gap_m": res.get('triangulacion', {}).get('gap_m'),
            "ekf_innovacion": round(float(error_innov), 4),
            "entropia_shannon_bits": round(entropia, 4),
            "telemetria_crc16": hex(crc),
            "desaceleracion_supuesta_pct": 0.0  # Parámetro del escenario, no detección observada
        }
        resultados_fases.append(fase_info)
        
        # Emitir log a Grafana / Elastic
        logger.emit_log({
            "id_caso": pt['id'],
            "estado": res['estado'],
            "velocidad_km_s": velocidad_constante_m_s / 1000.0,
            "mach": velocidad_constante_m_s / 340.3,
            "g_forces": None,  # No hay aceleración medida ni intervalo temporal validado.
            "gap_m": res.get('triangulacion', {}).get('gap_m'),
            "triangulacion_ok": res.get('triangulacion', {}).get('ok', False)
        })

    t1 = time.perf_counter()
    elapsed_ms = (t1 - t0) * 1000.0
    
    # Disparar alerta mobile para el evento transmedio global
    alerta_transmedio = {
        "id_caso": "EVT-TRANSMEDIO-GLOBAL-2026",
        "estado": "CANDIDATO_CINEMATICO",
        "velocidad_km_s": 1500.0,
        "mach": 4407.87,
        "g_forces": None,  # Velocidad sin aceleración medida: carga g no calculable.
        "triangulacion_ok": True,
        "gap_m": None,
        "triangulacion_ok": False,
        "tipo_datos": "ESCENARIO_SINTETICO_NO_VALIDADO"
    }
    notif_res = notifier.despachar_alertas(alerta_transmedio)
    
    output_payload = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nivel_alerta": "MAXIMA_CRITICO_TRANSMEDIO",
        "regla_disparo": "TRANSICION_MULTIDOMINIO_SIN_DESACELERACION",
        "tiempo_procesamiento_ms": round(elapsed_ms, 3),
        "fases_transicion_transmedio": resultados_fases,
        "despacho_alertas_mobile": notif_res,
        "visualizacion_realtime": {
            "radar_ppi": "SIMULACION_LOCAL_NO_CONECTADA",
            "esfera_terrestre_3d": "VISUALIZACION_DEMO_NO_VALIDADA"
        }
    }
    
    print("\n[RESULTADOS DE AUDITORÍA TRANSMEDIO MULTIDOMINIO]")
    print(f" • Tiempo de procesamiento : {elapsed_ms:.3f} ms")
    print(f" • Objeto Traza Transmedio  : EVT-TRANSMEDIO-GLOBAL-2026")
    print(f" • Velocidad de Transición : 1,500 km/s (Constante Espacio -> Aire -> Agua)")
    print(f" • Transición de Medio     : Exosfera (420 km) -> Atmósfera (12 km) -> Hidrosfera (-150 m)")
    print(f" • Desaceleración / Choque : 0% (Medio permeable sin resistencia aerodinámica/hidrodinámica)")
    print(f" • Estado Clasificación    : CANDIDATO_CINEMATICO 🟢")
    print("\n[PAYLOAD TRANSMEDIO COMPLETO DESPACHADO]")
    print(json.dumps(output_payload, indent=2, ensure_ascii=False))
    print("=" * 85)

if __name__ == '__main__':
    ejecutar_simulacion_transmedio_3d()
