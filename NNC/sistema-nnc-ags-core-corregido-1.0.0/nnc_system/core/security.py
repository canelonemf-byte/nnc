"""Utilidades de autenticación HMAC para pruebas locales. No implementa JWT ni TLS."""
import hashlib
import hmac
import json
import os
import time

class SecurityManager:
    def __init__(self, config_path="security_config.json"):
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {"grpc_security": {"enable_tls": False, "enable_mtls": False}, "rest_security": {"enable_jwt": False, "token_expiration_minutes": 60}}

    def _expiry_seconds(self):
        minutes = self.config.get("rest_security", {}).get("token_expiration_minutes", 60)
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = 60
        return max(1, min(minutes, 1440)) * 60

    def generate_demo_token(self, secret_key: str) -> str:
        if not secret_key or len(secret_key) < 16:
            raise ValueError("La clave debe tener al menos 16 caracteres")
        issued = int(time.time())
        payload = str(issued)
        sig = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"Bearer {payload}.{sig}"

    def verify_token(self, token: str, secret_key: str) -> bool:
        if not token or not secret_key or not token.startswith("Bearer "):
            return False
        try:
            payload, signature = token[7:].split(".", 1)
            issued = int(payload)
        except (ValueError, TypeError):
            return False
        now = int(time.time())
        if issued > now + 30 or now - issued > self._expiry_seconds():
            return False
        expected = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def get_grpc_ssl_credentials_info(self):
        cfg = self.config.get("grpc_security", {})
        cert_paths = [cfg.get("cert_chain_path"), cfg.get("private_key_path"), cfg.get("root_ca_path")]
        enabled = bool(cfg.get("enable_tls", False))
        files_present = all(path and os.path.isfile(path) for path in cert_paths)
        return {"tls_enabled_configured": enabled, "mtls_enabled_configured": bool(cfg.get("enable_mtls", False)), "certificate_files_present": files_present, "tls_operational": enabled and files_present, "note": "La presencia de archivos no demuestra por sí sola que una conexión TLS funcione."}
