from http.server import BaseHTTPRequestHandler
from api._common import send

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send(self, 200, {"status": "ok", "service": "nnc-live", "evidencia_deteccion": "E1 (no validada)",
                         "autoria": "Lázaro López Paz con asistencia de IA"})
