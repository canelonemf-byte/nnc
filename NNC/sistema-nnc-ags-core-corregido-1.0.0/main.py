#!/usr/bin/env python3
from core.ags_core_lora_agents import MetaControllerAGsCore

if __name__ == '__main__':
    print('==========================================================')
    print('SISTEMA NNC + AGs-Core + LoRA: RUNTIME MULTIDOMINIO (v1.0.0)')
    print('==========================================================')
    meta = MetaControllerAGsCore()
    test_evt = {
        'id': 'EVT-DEMO-LAUNCH',
        'dominio': 'Atmosfera',
        'ecef': (4792306.7, 171538.3, 4192011.0),
        'posA': [0,0,0], 'obsA': (33.72, 22.56),
        'posB': [8000,0,0], 'obsB': (-33.73, 22.61),
        'v_m_s': 2000000.0
    }
    res = meta.auditar_evento(test_evt)
    print(f'Prueba de inicio => ID: {res["id"]} | Estado: {res["estado"]}')
    print('==========================================================')
    print('Demostración local completada. No implica conexión a sensores ni validación de datos reales.')
