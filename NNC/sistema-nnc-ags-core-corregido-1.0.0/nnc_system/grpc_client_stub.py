#!/usr/bin/env python3
"""Mock de cliente para pruebas de interfaz; no crea un canal gRPC real."""
import os

class AGsCoreGRPCClientStub:
    def __init__(self, host="localhost", port=50051, use_tls=False, auth_token=None):
        self.host = host
        self.port = int(port)
        self.use_tls = bool(use_tls)
        self.auth_token = auth_token or os.getenv("NNC_API_TOKEN")
        self.channel_active = False
        print("[gRPC mock] Modo simulación: no existe conexión gRPC real en esta distribución.")

    def auditar_evento(self, id_evento, dominio, ecef, posA, posB, obsA, obsB, v_m_s, aceleracion_m_s2=None):
        v = float(v_m_s)
        if v < 0:
            raise ValueError("v_m_s no puede ser negativa")
        return {
            "id_evento": id_evento,
            "estado": "SIMULACION_NO_VALIDADA",
            "modo": "MOCK_SIN_CANAL_GRPC",
            "triangulacion": {"ok": False, "gap_m": None, "motivo": "La triangulación real debe ejecutarse en el controlador con posiciones ENU compatibles."},
            "cinematica": {
                "v_km_s": v / 1000.0,
                "mach": v / 340.3,
                "g_fuerza": float(aceleracion_m_s2) / 9.80665 if aceleracion_m_s2 is not None else None,
            },
        }

    def cargar_adaptador_lora(self, nombre_adaptador, rank=8, alpha=16.0):
        if rank <= 0 or alpha <= 0:
            raise ValueError("rank y alpha deben ser positivos")
        params = 2 * int(rank) * 4096
        return {"nombre_adaptador": nombre_adaptador, "cargado_ok": False, "modo": "SOLO_ESTIMACION_MEMORIA_SIN_CARGA_REAL", "parametros_estimados": params, "memoria_mb_fp32_estimada": params * 4 / (1024 * 1024)}

if __name__ == "__main__":
    client = AGsCoreGRPCClientStub()
    print(client.auditar_evento("DEMO", "Espacio", (0, 0, 0), [0,0,0], [8000,0,0], (0,0), (0,0), 1500.0))
