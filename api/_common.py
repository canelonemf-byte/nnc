"""Servidor NNC en Vercel (Python serverless). Lázaro López Paz con asistencia de IA. MIT.
Reutiliza nnc_system/core/live_sources.py (stdlib). Sin secretos en el código."""
import json, os, sys
_CORE = os.path.join(os.path.dirname(__file__), "..", "NNC", "sistema-nnc-ags-core-corregido-1.0.0", "nnc_system")
sys.path.insert(0, os.path.abspath(_CORE))
from core import live_sources  # noqa: E402

DEFAULT_ORIGINS = "https://quartz-trail-summit-turbo.grok.me,https://drift-hazel-urban-dawn.grok.me"
def allowed_origins():
    return [o.strip() for o in os.getenv("NNC_ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]

def send(h, code, payload):
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    h.send_response(code)
    origin = h.headers.get("Origin", "")
    if origin in allowed_origins():
        h.send_header("Access-Control-Allow-Origin", origin)
        h.send_header("Vary", "Origin")
        h.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "public, s-maxage=15, stale-while-revalidate=30")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)
