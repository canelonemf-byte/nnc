from .ecef_bowring import validar_ingreso_ecef
from .triangulacion_enu import triangulacion_azel
from .advanced_math_physics import ExtendedKalmanFilter3D, corregir_refraccion_atmosferica, calcular_entropia_cinematica, verificar_crc16
from .satellite_sensor_network import SatelliteSensorNetwork

class MetaControllerAGsCore:
    def __init__(self):
        self.ekf = ExtendedKalmanFilter3D(dt=0.1)
        self.sat_net = SatelliteSensorNetwork()

    def auditar_evento(self, evento):
        if not isinstance(evento, dict):
            raise TypeError("evento debe ser un diccionario")
        try:
            x, y, z = evento.get('ecef', (0, 0, 0))
        except (TypeError, ValueError):
            return {'id': evento.get('id'), 'estado': 'RECHAZADO_INGRESO', 'motivo': 'ecef debe contener tres coordenadas'}
        ok_ing, st_ing, msg_ing = validar_ingreso_ecef(x, y, z)
        if not ok_ing:
            return {'id': evento.get('id'), 'estado': st_ing, 'motivo': msg_ing}
            
        posA, posB = evento.get('posA', [0,0,0]), evento.get('posB', [8000,0,0])
        azA, elA = evento.get('obsA', (0,0))
        azB, elB = evento.get('obsB', (0,0))
        
        dominio = evento.get('dominio', 'Exosfera')
        try:
            altitud_m = float(evento.get('altitud_m', 420000.0))
            lat_ref = float(evento.get('lat', 41.3879))
            lon_ref = float(evento.get('lon', 2.1699))
            import math
            if not all(math.isfinite(v) for v in (altitud_m, lat_ref, lon_ref)) or not -90 <= lat_ref <= 90 or not -180 <= lon_ref <= 180:
                raise ValueError
        except (TypeError, ValueError):
            return {'id': evento.get('id'), 'estado': 'RECHAZADO_INGRESO', 'motivo': 'altitud, latitud o longitud inválidas'}
        if evento.get('aceleracion_m_s2') is not None:
            try:
                acceleration_input = float(evento['aceleracion_m_s2'])
                if not math.isfinite(acceleration_input):
                    raise ValueError
            except (TypeError, ValueError):
                return {'id': evento.get('id'), 'estado': 'RECHAZADO_INGRESO', 'motivo': 'aceleracion_m_s2 debe ser finita y numérica'}
        else:
            acceleration_input = None
        
        # En Exosfera/Espacio (h > 100km), la refracción troposférica es despreciable
        if altitud_m > 100000.0:
            rA_deg, rB_deg = 0.0, 0.0
            elA_corregido, elB_corregido = elA, elB
        else:
            elA_corregido, rA_deg = corregir_refraccion_atmosferica(elA, 0.5)
            elB_corregido, rB_deg = corregir_refraccion_atmosferica(elB, 0.5)
        
        ok_tri, p_mid, tA, tB, gap_m, msg_tri = triangulacion_azel(posA, azA, elA_corregido, posB, azB, elB_corregido)
        try:
            v_m_s = float(evento.get('v_m_s', 0.0))
        except (TypeError, ValueError):
            return {'id': evento.get('id'), 'estado': 'RECHAZADO_INGRESO', 'motivo': 'v_m_s debe ser numérico'}
        import math
        if not math.isfinite(v_m_s) or v_m_s < 0:
            return {'id': evento.get('id'), 'estado': 'RECHAZADO_INGRESO', 'motivo': 'v_m_s debe ser finita y no negativa'}
        
        # Estimación EKF 3D
        self.ekf.predict()
        if p_mid is not None:
            x_est, error_innov = self.ekf.update([p_mid[0], p_mid[1], p_mid[2]])
        else:
            x_est, error_innov = self.ekf.x, 999.0
        
        # Cálculo de Entropía de Shannon del perfil
        historia_v = evento.get('historia_v', [v_m_s, v_m_s*0.99, v_m_s*1.01])
        entropia = calcular_entropia_cinematica(historia_v)
        
        # Verificación CRC-16 de la trama
        data_bytes = f"{evento.get('id')}:{v_m_s}:{x}:{y}:{z}".encode('utf-8')
        crc_val = verificar_crc16(data_bytes)
        
        # Consulta en tiempo real de la Red Integrada de Sensores Satelitales (soporta tormenta solar)
        sim_storm = evento.get('simular_tormenta_solar', False)
        kp_over = evento.get('kp_override', None)
        sat_telemetry = self.sat_net.consultar_sensores_satelitales(
            lat_ref, lon_ref, altitud_m, 
            simular_tormenta_solar=sim_storm, 
            kp_override=kp_over
        )
        
        # Evaluación Filtro H3 (Catálogo TLE / NORAD para Objetos Espaciales)
        tle_info = evento.get('tle_match', None)
        if tle_info:
            estado = 'EXPLICADO'
            filtro_h3 = f"COINCIDENCIA_NORAD_TLE ({tle_info})"
        elif v_m_s > 1000.0:
            estado = 'CANDIDATO_CINEMATICO'
            filtro_h3 = "SIN_COINCIDENCIA_NORAD_TLE (Traza no correlacionada)"
        elif ok_tri and v_m_s <= 350.0:
            estado = 'DENTRO_DE_ENVOLVENTE'
            filtro_h3 = "ORBITA_BAJA_CONVENCIONAL"
        elif not ok_tri:
            estado = 'CINEMATICA_NO_CERRADA'
            filtro_h3 = "TRIANGULACION_INCOMPLETA"
        else:
            estado = 'ABIERTO'
            filtro_h3 = "EVALUACION_PENDIENTE"
            
        v_km_s = v_m_s / 1000.0
        mach_val = v_m_s / 340.3
        # La velocidad no permite inferir aceleración ni fuerzas g.
        acceleration_m_s2 = acceleration_input
        g_forces_val = (acceleration_m_s2 / 9.80665) if acceleration_m_s2 is not None else None
            
        return {
            'id': evento.get('id'),
            'id_caso': evento.get('id'),
            'dominio': dominio,
            'estado': estado,
            'filtro_h3_tle': filtro_h3,
            'velocidad_km_s': v_km_s,
            'mach': mach_val,
            'g_forces': g_forces_val,
            'triangulacion_ok': ok_tri,
            'gap_m': gap_m,
            'triangulacion': {
                'ok': ok_tri, 
                'gap_m': gap_m, 
                'refraccion_deg': (rA_deg + rB_deg) / 2.0
            },
            'cinematica': {
                'altitud_km': altitud_m / 1000.0,
                'v_km_s': v_km_s, 
                'mach': mach_val,
                'entropia_shannon': round(entropia, 4),
                'ekf_innovacion': round(float(error_innov), 4)
            },
            'red_sensores_satelitales': sat_telemetry,
            'telemetria': {
                'crc16': hex(crc_val)
            }
        }
