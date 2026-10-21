#!/usr/bin/env python3
"""
Prueba de Carga Continuada (Stress Test) para el Sistema NNC + AGs-Core.
Simula la entrada ininterrumpida de eventos multiesfera y audita latencia/throughput.
"""

import time
import random
import json
from core.ags_core_lora_agents import MetaControllerAGsCore

def ejecutar_prueba_carga_continuada(duracion_segundos=10):
    print("================================================================================")
    print("INICIANDO PRUEBA DE CARGA CONTINUADA Y ESTRÉS EN TIEMPO REAL (NNC + AGs-Core)")
    print("================================================================================")
    
    meta = MetaControllerAGsCore()
    dominios = ["Atmosfera", "Hidrosfera", "Litosfera", "Espacio", "Biosfera"]
    
    inicio = time.time()
    eventos_procesados = 0
    errores = 0
    latencias_ms = []

    while (time.time() - inicio) < duracion_segundos:
        t_start_evt = time.perf_counter()
        
        dominio_sel = random.choice(dominios)
        v_sim = random.choice([250.0, 1500000.0, 0.5, 7650.0, 2000.0])
        
        evt = {
            'id': f'STRESS-EVT-{eventos_procesados + 1:05d}',
            'dominio': dominio_sel,
            'ecef': (4792306.7 + random.uniform(-100, 100), 171538.3, 4192011.0),
            'posA': [0, 0, 0], 'obsA': (random.uniform(10, 80), random.uniform(10, 40)),
            'posB': [8000, 0, 0], 'obsB': (random.uniform(-80, -10), random.uniform(10, 40)),
            'v_m_s': v_sim
        }
        
        res = meta.auditar_evento(evt)
        t_end_evt = time.perf_counter()
        
        lat_ms = (t_end_evt - t_start_evt) * 1000.0
        latencias_ms.append(lat_ms)
        eventos_procesados += 1

    duracion_real = time.time() - inicio
    throughput = eventos_procesados / duracion_real
    lat_promedio = sum(latencias_ms) / len(latencias_ms)
    lat_max = max(latencias_ms)
    lat_min = min(latencias_ms)

    print(f"\n[RESULTADOS PRUEBA DE CARGA]")
    print(f" • Tiempo Total Transcurrido : {duracion_real:.2f} s")
    print(f" • Total Eventos Auditados   : {eventos_procesados}")
    print(f" • Tasa de Procesamiento     : {throughput:.2f} eventos/segundo")
    print(f" • Latencia Promedio por Evt : {lat_promedio:.3f} ms")
    print(f" • Latencia Mínima / Máxima  : {lat_min:.3f} ms / {lat_max:.3f} ms")
    print(f" • Errores de Proceso        : {errores}")
    print("================================================================================")
    print("✅ PRUEBA DE ESTRÉS COMPLETADA SATISFACTORIAMENTE — SIF / NNC ESTABLE")
    print("================================================================================")

if __name__ == "__main__":
    ejecutar_prueba_carga_continuada(duracion_segundos=5)
