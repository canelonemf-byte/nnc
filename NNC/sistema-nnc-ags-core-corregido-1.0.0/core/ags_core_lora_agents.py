from .ecef_bowring import validar_ingreso_ecef
from .triangulacion_enu import triangulacion_azel

class MetaControllerAGsCore:
    def auditar_evento(self, evento):
        x, y, z = evento.get('ecef', (0, 0, 0))
        ok_ing, st_ing, msg_ing = validar_ingreso_ecef(x, y, z)
        if not ok_ing:
            return {'id': evento.get('id'), 'estado': st_ing, 'motivo': msg_ing}
            
        posA, posB = evento.get('posA', [0,0,0]), evento.get('posB', [8000,0,0])
        azA, elA = evento.get('obsA', (0,0))
        azB, elB = evento.get('obsB', (0,0))
        ok_tri, p_mid, tA, tB, gap_m, msg_tri = triangulacion_azel(posA, azA, elA, posB, azB, elB)
        try:
            v_m_s = float(evento.get('v_m_s', 0.0))
            import math
            if not math.isfinite(v_m_s) or v_m_s < 0:
                raise ValueError
        except (TypeError, ValueError):
            return {'id': evento.get('id'), 'estado': 'RECHAZADO_INGRESO', 'motivo': 'v_m_s debe ser finita y no negativa'}
        
        if v_m_s > 1000.0:
            estado = 'CANDIDATO_CINEMATICO'
        elif ok_tri and v_m_s <= 350.0:
            estado = 'DENTRO_DE_ENVOLVENTE'
        elif not ok_tri:
            estado = 'CINEMATICA_NO_CERRADA'
        else:
            estado = 'ABIERTO'
            
        return {
            'id': evento.get('id'),
            'dominio': evento.get('dominio'),
            'estado': estado,
            'triangulacion': {'ok': ok_tri, 'gap_m': gap_m},
            'cinematica': {'v_km_s': v_m_s / 1000.0, 'mach': v_m_s / 340.3, 'g_forces': (float(evento['aceleracion_m_s2']) / 9.80665 if evento.get('aceleracion_m_s2') is not None else None)}
        }
