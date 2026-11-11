#!/usr/bin/env python3
"""WebSocket de tráfico cooperativo + HTTP de la vista Ojo de Dios. No etiqueta FANI. Silencio no es objeto.

Autoría: Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia IA.
Rutas HTTP (solo GET):
  /  /radar.html  /index.html  /dashboard_3d.html     páginas de la beta (lista blanca)
  /api/ojo?radio_km=&alt_min_ft=&alt_max_ft=&el_min_deg=&edad_max_s=   vista Ojo de Dios (JSON)
  /api/ojo/historial?n=50                              historial JSONL local
  /api/ojo/salud                                       módulo ojo_de_dios disponible o no
  /ws/flujo                                            WebSocket (sin cambios de formato)
Arranque (python con httpx+skyfield, p. ej. el venv de ojo_de_dios; módulo vía OJO_DE_DIOS_SRC
o, por defecto, <repo>/ojo_de_dios/src):
  NNC_WS_PORT=8765 python ws_vivo.py
"""
import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

HOST = os.environ.get("NNC_WS_HOST", "127.0.0.1")
PORT = int(os.environ.get("NNC_WS_PORT", "8765"))
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
UA = {"User-Agent": "NNC-LLP/1.0"}
PRAT = "https://api.adsb.lol/v2/lat/41.2974/lon/2.0833/dist/120"
ISS = "https://api.wheretheiss.at/v1/satellites/25544"

HERE = os.path.dirname(os.path.abspath(__file__))
RADAR = os.path.join(HERE, "radar.html")
PAGINAS = {"/": "radar.html", "/radar.html": "radar.html", "/index.html": "index.html", "/dashboard_3d.html": "dashboard_3d.html",
           "/ojo_dios.js": "ojo_dios.js"}

try:
    import ojo_vista  # resuelve ojo_de_dios: OJO_DE_DIOS_SRC -> <repo>/ojo_de_dios/src -> ../ojo_de_dios/src
except Exception as _e:  # noqa: BLE001
    ojo_vista = None
    OJO_ERR = str(_e)[:200]
else:
    OJO_ERR = ""

STATUS_TXT = {200: "OK", 404: "Not Found", 405: "Method Not Allowed", 422: "Unprocessable Entity", 500: "Internal Server Error", 503: "Service Unavailable"}


def http_send(conn, code, body, ctype):
    head = (
        f"HTTP/1.1 {code} {STATUS_TXT.get(code, 'OK')}\r\n"
        f"Content-Type: {ctype}\r\n"
        "Cache-Control: no-store\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "X-Autoria: Lazaro Lopez Paz, El Prat de Llobregat, Barcelona, Espana, con asistencia IA\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    conn.sendall(head + body)
    conn.close()


def http_json(conn, code, obj):
    http_send(conn, code, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), "application/json; charset=utf-8")


def http_radar(conn, name="radar.html"):
    try:
        body = open(os.path.join(HERE, name), "rb").read()
        code = 200
    except Exception:
        body, code = (name + " no encontrado").encode(), 404
    ctype = "application/javascript; charset=utf-8" if name.endswith(".js") else "text/html; charset=utf-8"
    http_send(conn, code, body, ctype)


def http_route(conn, method, target):
    u = urlsplit(target)
    path, qs = u.path, parse_qs(u.query, keep_blank_values=True)
    if method != "GET":
        return http_json(conn, 405, {"ok": False, "error": "solo GET"})
    if path in PAGINAS:
        return http_radar(conn, PAGINAS[path])
    if path.startswith("/api/ojo"):
        if ojo_vista is None or not getattr(ojo_vista, "DISPONIBLE", False):
            return http_json(conn, 503, {"ok": False, "error": "modulo_ojo_de_dios_no_disponible",
                                         "detalle": OJO_ERR or getattr(ojo_vista, "IMPORT_ERROR", ""),
                                         "arranque": "pip install -r ojo_de_dios/requirements.txt && python ws_vivo.py (o OJO_DE_DIOS_SRC=...)"})
        if path == "/api/ojo":
            code, body = ojo_vista.vista_segura(qs)
            return http_json(conn, code, body)
        if path == "/api/ojo/historial":
            try:
                n = int((qs.get("n") or ["50"])[0])
            except ValueError:
                return http_json(conn, 422, {"ok": False, "error": "n no entero"})
            return http_json(conn, 200, {"ok": True, "historial": ojo_vista.leer_historial(n), "archivo": str(ojo_vista.HIST_FILE)})
        if path == "/api/ojo/salud":
            return http_json(conn, 200, {"ok": True, "disponible": True, "autoria": ojo_vista.AUTORIA, "ojo_src": ojo_vista.OJO_SRC})
    return http_json(conn, 404, {"ok": False, "error": "ruta no encontrada",
                                 "rutas": sorted(PAGINAS) + ["/api/ojo", "/api/ojo/historial", "/api/ojo/salud", "/ws/flujo"]})


lock = threading.Lock()
clients = set()  # corregido: en el original no estaba definido (NameError en broadcast/serve)
latest = {"tipo": "vacio"}


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def pulso():
    ac = []
    iss = None
    err = []
    try:
        data = fetch(PRAT)
        for a in data.get("ac") or []:
            if a.get("lat") is None or a.get("lon") is None:
                continue
            ac.append({
                "hex": a.get("hex"),
                "flight": (a.get("flight") or "").strip(),
                "t": a.get("t"),
                "lat": a.get("lat"),
                "lon": a.get("lon"),
                "alt": a.get("alt_baro"),
                "gs": a.get("gs"),
                "track": a.get("track"),
                "mach": a.get("mach"),
                "baro_rate": a.get("baro_rate"),
            })
    except Exception as e:
        err.append("adsb:" + str(e)[:80])
    try:
        iss = fetch(ISS)
    except Exception as e:
        err.append("iss:" + str(e)[:80])
    return {
        "tipo": "flujo",
        "utc": datetime.now(timezone.utc).isoformat(),
        "es_fani": False,
        "nota": "Tráfico con baliza o ISS. Silencio no se emite.",
        "n": len(ac),
        "ac": ac,
        "iss": None if not iss else {
            "lat": iss.get("latitude"),
            "lon": iss.get("longitude"),
            "alt_km": iss.get("altitude"),
            "v_kmh": iss.get("velocity"),
            "estado": "EXPLICADO",
        },
        "errores": err,
    }


def encode(text):
    data = text.encode()
    n = len(data)
    if n < 126:
        head = bytes([0x81, n])
    elif n < 65536:
        head = bytes([0x81, 126]) + struct.pack("!H", n)
    else:
        head = bytes([0x81, 127]) + struct.pack("!Q", n)
    return head + data


def broadcast(payload):
    frame = encode(json.dumps(payload, separators=(",", ":")))
    dead = []
    with lock:
        socks = list(clients)
    for s in socks:
        try:
            s.sendall(frame)
        except Exception:
            dead.append(s)
    if dead:
        with lock:
            for s in dead:
                clients.discard(s)


def pump():
    global latest
    while True:
        latest = pulso()
        broadcast(latest)
        time.sleep(8)


def handshake(conn, buf):
    head = buf.decode("latin1", "replace")
    parts = head.split("\r\n", 1)[0].split(" ")
    method, target = (parts[0], parts[1]) if len(parts) >= 2 else ("", "/")
    if "upgrade: websocket" not in head.lower():
        http_route(conn, method, target)
        return False
    key = ""
    for line in head.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    conn.sendall(
        ("HTTP/1.1 101 Switching Protocols\r\n"
         "Upgrade: websocket\r\n"
         "Connection: Upgrade\r\n"
         f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode()
    )
    return True


def serve(conn):
    try:
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buf += chunk
        if not handshake(conn, buf):
            return
        with lock:
            clients.add(conn)
        if latest.get("tipo") != "vacio":
            conn.sendall(encode(json.dumps(latest, separators=(",", ":"))))
        while True:
            b = conn.recv(2)
            if not b:
                break
            # descartar frames del cliente (ping/close)
            ln = b[1] & 127
            if ln == 126:
                ln = struct.unpack("!H", conn.recv(2))[0]
            elif ln == 127:
                ln = struct.unpack("!Q", conn.recv(8))[0]
            mask = conn.recv(4) if b[1] & 128 else b""
            rest = ln
            while rest:
                chunk = conn.recv(rest)
                if not chunk:
                    return
                rest -= len(chunk)
            if b[0] & 15 == 8:
                break
    except Exception:
        pass
    finally:
        with lock:
            clients.discard(conn)
        try:
            conn.close()
        except Exception:
            pass


def main():
    threading.Thread(target=pump, daemon=True).start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(8)
    print(f"ws://{HOST}:{PORT}/ws/flujo", flush=True)
    while True:
        conn, _ = sock.accept()
        threading.Thread(target=serve, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
