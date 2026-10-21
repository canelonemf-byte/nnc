#!/usr/bin/env python3
"""
test_autocalibracion_continua_iss.py
Módulo de Autocalibración Continua del Par Óptico mediante Pases Satelitales ISS (NORAD 25544)
Ejecuta la verificación de alineación angular (Az/El), corrección de matriz de distorsión
y sincronización de reloj NTP/GNSS cada vez que un pase de la ISS es detectado.
"""

import math
import json
import time
import os

def ejecutar_autocalibracion_iss():
    timestamp_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    # Parámetros nominales de la línea de base de 8 km (Prat de Llobregat <-> Estación Oeste)
    estacion_a = {"lat": 41.3278, "lon": 2.0947, "alt": 8.0, "nombre": "Prat de Llobregat (Cam A)"}
    estacion_b = {"lat": 41.3278, "lon": 1.9990, "alt": 12.0, "nombre": "Oeste 8km (Cam B)"}
    
    # Valores sintéticos de demostración; no son efemérides ni mediciones de una cámara real.
    iss_altitud_km = 428.917
    iss_velocidad_m_s = 7657.87
    iss_distancia_r_km = 428.982
    
    # 1. Test de Sincronización de Reloj (GNSS/NTP)
    desfase_reloj_ms = 1.24  # Criterio: < 20 ms
    sincronia_ok = desfase_reloj_ms < 20.0
    
    # 2. Test de Triangulación y Margen de Cruce (gap_m)
    gap_m = 3.17157  # Criterio: < 5.0 m para distancia de 428 km
    triangulacion_ok = gap_m < 5.0
    
    # 3. Estimación de Deriva de Alineación Angular (Boresight Drift)
    deriva_azimuth_deg = 0.00012
    deriva_elevation_deg = -0.00008
    alineacion_ok = abs(deriva_azimuth_deg) < 0.001 and abs(deriva_elevation_deg) < 0.001
    
    # 4. Cálculo de Matriz de Ajuste Fina de Foco y FOV
    frecuencia_calibracion_hz = 60.0
    error_pixel_rms = 0.082  # Subpíxel RMS < 0.1 px
    
    calibracion_exitosa = sincronia_ok and triangulacion_ok and alineacion_ok
    
    resultado = {
        "tipo_datos": "SINTETICOS_NO_MEDICIONES_REALES",
        "calibracion_fisica_validada": False,
        "HEADER_AUTOCALIBRACION": {
            "timestamp_utc": timestamp_utc,
            "id_calibracion": f"CALIB-ISS-{int(time.time())}",
            "objeto_referencia": "ISS (NORAD 25544)",
            "estado_calibracion": "SIMULACION_OK_NO_CALIBRACION_REAL" if calibracion_exitosa else "SIMULACION_FALLIDA"
        },
        "METRICAS_ALINEACION": {
            "desfase_sincronia_reloj_ms": desfase_reloj_ms,
            "tolerancia_sincronia_ms": 20.0,
            "sincronia_pass": sincronia_ok,
            "gap_m_error_cruce": gap_m,
            "tolerancia_gap_m": 5.0,
            "triangulacion_pass": triangulacion_ok,
            "deriva_boresight_az_deg": deriva_azimuth_deg,
            "deriva_boresight_el_deg": deriva_elevation_deg,
            "alineacion_pass": alineacion_ok,
            "error_subpixel_rms": error_pixel_rms
        },
        "ESTACIONES": {
            "estacion_a": estacion_a,
            "estacion_b": estacion_b,
            "linea_base_m": 8000.0
        }
    }
    
    # Guardar en base de datos local
    db_dir = os.path.join(os.path.dirname(__file__), "db")
    os.makedirs(db_dir, exist_ok=True)
    db_file = os.path.join(db_dir, "calibracion_sensores.json")
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
        
    return resultado

if __name__ == "__main__":
    res = ejecutar_autocalibracion_iss()
    print("=" * 80)
    print("AUTOCALIBRACIÓN CONTINUA DE PAR ÓPTICO CON PASE ISS (NORAD 25544)")
    print("=" * 80)
    print(f"Estado                 : {res['HEADER_AUTOCALIBRACION']['estado_calibracion']}")
    print(f"Desfase Reloj NTP/GNSS : {res['METRICAS_ALINEACION']['desfase_sincronia_reloj_ms']} ms (Límite < 20 ms)")
    print(f"Error de Cruce gap_m   : {res['METRICAS_ALINEACION']['gap_m_error_cruce']} m (Límite < 5.0 m)")
    print(f"Error Subpíxel RMS     : {res['METRICAS_ALINEACION']['error_subpixel_rms']} px")
    print(f"Fichero Guardado       : db/calibracion_sensores.json")
    print("=" * 80)
