#!/usr/bin/env python3
"""API REST local para estado y auditoría de eventos NNC (sin afirmar fuentes live)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from core.ags_core_lora_agents import MetaControllerAGsCore

HOST = os.getenv("NNC_HOST", "127.0.0.1")
PORT = int(os.getenv("NNC_PORT", "8000"))
API_TOKEN = os.getenv("NNC_API_TOKEN", "")
if API_TOKEN and len(API_TOKEN) < 32:
    raise SystemExit("NNC_API_TOKEN debe tener al menos 32 caracteres; genere un secreto aleatorio.")

class Handler(BaseHTTPRequestHandler):
    server_version = "NNC-AGsCore/1.0"

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "service": "nnc-ags-core", "data_mode": "simulation_or_user_supplied", "external_sources_connected": False})
        if self.path == "/":
            return self._send(200, {"service": "NNC + AGs-Core", "endpoints": ["GET /health", "GET /api/status", "POST /api/audit"]})
        if self.path == "/api/status":
            return self._send(200, {"status": "running", "audit_endpoint_auth_required": True, "external_sources_connected": False, "scientific_validation": "not_claimed"})
        return self._send(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/api/audit":
            return self._send(404, {"error": "not_found"})
        if not API_TOKEN:
            return self._send(503, {"error": "audit_api_disabled", "detail": "Configure NNC_API_TOKEN antes de habilitar auditorías HTTP."})
        auth = self.headers.get("Authorization", "")
        import hmac
        if not hmac.compare_digest(auth, "Bearer " + API_TOKEN):
            return self._send(401, {"error": "unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                return self._send(413, {"error": "invalid_body_size"})
            event = json.loads(self.rfile.read(length))
            if not isinstance(event, dict):
                return self._send(400, {"error": "json_object_required"})
            # Un controlador por petición evita compartir el estado mutable del EKF entre hilos.
            result = MetaControllerAGsCore().auditar_evento(event)
            return self._send(200, {"result": result, "data_mode": "user_supplied_plus_simulated_components", "external_sources_connected": False})
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send(400, {"error": "invalid_json"})
        except Exception as exc:
            return self._send(400, {"error": "invalid_event", "detail": str(exc)})

    def log_message(self, fmt, *args):
        # No registrar cabeceras de autorización ni contenido sensible.
        print("%s - %s" % (self.client_address[0], fmt % args))

if __name__ == "__main__":
    print(f"NNC REST escuchando en http://{HOST}:{PORT}; /api/audit requiere NNC_API_TOKEN")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
