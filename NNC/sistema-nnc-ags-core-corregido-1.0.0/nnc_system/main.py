#!/usr/bin/env python3
from core.ags_core_lora_agents import MetaControllerAGsCore
from core.security import SecurityManager
from suite_autotest_calibracion_maestra import ejecutar_suite_calibracion_maestra

if __name__ == '__main__':
    print('==========================================================')
    print('SISTEMA NNC + AGs-Core + LoRA: RUNTIME MULTIDOMINIO (v24.0.0)')
    print('==========================================================')
    
    # 1. Ejecución de la Suite Completa de Autotests y Calibración del Sistema
    ejecutar_suite_calibracion_maestra()
    
    # 2. Auditoría del Meta-Controlador
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
    
    # 3. Verificación del Módulo de Seguridad gRPC / REST
    sec = SecurityManager("security_config.json")
    sec_info = sec.get_grpc_ssl_credentials_info()
    demo_token = sec.generate_demo_token("clave_demo_local_no_usar_en_produccion_2026")
    token_valid = sec.verify_token(demo_token, "clave_demo_local_no_usar_en_produccion_2026")
    
    print(f'Seguridad TLS => configurado: {sec_info["tls_enabled_configured"]} | certificados presentes: {sec_info["certificate_files_present"]} | TLS operativo verificado: {sec_info["tls_operational"]}')
    print(f'Validación token HMAC de demostración => válido: {token_valid} (no es JWT; no usar clave de demo en producción)')
    
    print('==========================================================')
    print('Ejecución de demostración completada. La suite incluye escenarios simulados; no acredita operación con sensores reales.')
