import json
import os

class AlertNotifier:
    """
    Módulo de Notificaciones Instantáneas para Telegram y Slack.
    Despacha alertas críticas de eventos clasificados como CANDIDATO_CINEMATICO.
    """
    def __init__(self, config_path="security_config.json"):
        self.telegram_enabled = False
        self.slack_enabled = False
        self.config_path = config_path
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f).get("notificaciones", {})
            self.telegram_enabled = bool(cfg.get("enable_telegram")) and len(str(cfg.get("telegram_bot_token", ""))) >= 20 and not str(cfg.get("telegram_bot_token", "")).startswith("CONFIGURAR_") and bool(cfg.get("telegram_chat_id")) and not str(cfg.get("telegram_chat_id", "")).startswith("CONFIGURAR_")
            self.slack_enabled = bool(cfg.get("enable_slack")) and bool(cfg.get("slack_webhook_url")) and not str(cfg.get("slack_webhook_url", "")).startswith("CONFIGURAR_")
        except (OSError, ValueError, TypeError):
            pass

    def formato_mensaje_telegram(self, evento):
        v_km_s = evento.get("velocidad_km_s", 0.0)
        mach = evento.get("mach", 0.0)
        g_forces = evento.get("g_forces")
        g_text = f"{float(g_forces):,.1f} g" if g_forces is not None else "No calculada (sin aceleración medida)"
        caso_id = evento.get("id_caso", "DESCONOCIDO")
        
        msg = (
            f"🚨 ALERTA CRITICA NNC + AGs-CORE 🚨\n\n"
            f"ID Caso: {caso_id}\n"
            f"Estado: CANDIDATO_CINEMATICO\n"
            f"Velocidad: {v_km_s:,.1f} km/s (Mach {mach:,.1f})\n"
            f"Carga g: {g_text}\n"
            f"Triangulación 3D: {'Cerrada' if evento.get('triangulacion_ok') else 'Sin R'}\n"
            f"Filtro H0-H7: heurística no validada; requiere revisión independiente\n\n"
            f"Acción requerida: Verificación en panel de control."
        )
        return msg

    def formato_payload_slack(self, evento):
        v_km_s = evento.get("velocidad_km_s", 0.0)
        mach = evento.get("mach", 0.0)
        g_forces = evento.get("g_forces", 0.0)
        caso_id = evento.get("id_caso", "DESCONOCIDO")
        
        return {
            "text": f"ALERTA CRITICA: CANDIDATO_CINEMATICO DETECTADO [{caso_id}]",
            "velocidad_km_s": v_km_s,
            "mach": mach,
            "g_forces": g_forces,
            "estado": "CANDIDATO_CINEMATICO"
        }

    def despachar_alertas(self, evento):
        msg_tg = self.formato_mensaje_telegram(evento)
        payload_slack = self.formato_payload_slack(evento)
        return [
            {"canal": "Telegram", "status": "NO_CONFIGURADO" if not self.telegram_enabled else "NO_ENVIADO_POR_ESTE_MOCK", "mensaje": msg_tg},
            {"canal": "Slack", "status": "NO_CONFIGURADO" if not self.slack_enabled else "NO_ENVIADO_POR_ESTE_MOCK", "payload": payload_slack}
        ]
