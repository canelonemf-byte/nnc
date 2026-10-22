"""Test local del handler Vercel con CORS (sin red: fetch simulado SOLO en test)."""
import threading, json, urllib.request, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import HTTPServer
from api import live
from api._common import live_sources
live_sources.fetch_json = lambda url, timeout=15: (_ for _ in ()).throw(OSError("sin red en test"))
srv = HTTPServer(("127.0.0.1", 0), live.handler); threading.Thread(target=srv.serve_forever, daemon=True).start()
def get(origin):
    r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/api/live", headers={"Origin": origin}))
    return r.headers.get("Access-Control-Allow-Origin"), json.loads(r.read())
a, j = get("https://quartz-trail-summit-turbo.grok.me"); assert a == "https://quartz-trail-summit-turbo.grok.me"
a2, _ = get("https://drift-hazel-urban-dawn.grok.me"); assert a2 == "https://drift-hazel-urban-dawn.grok.me"
a3, _ = get("https://evil.example"); assert a3 is None
assert set(j["fuentes"]) == {"opensky", "iss", "met", "kp"} and "E1" in j["evidencia_deteccion"]
print("OK tests_deploy: CORS 2 dominios permitidos, otros denegados; estructura /api/live correcta")
