#!/usr/bin/env python3
"""WebSocket de tráfico cooperativo. No etiqueta FANI. Silencio no es objeto."""
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

HOST = os.environ.get("NNC_WS_HOST", "127.0.0.1")
PORT = int(os.environ.get("NNC_WS_PORT", "8765"))
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
UA = {"User-Agent": "NNC-LLP/1.0"}
PRAT = "https://api.adsb.lol/v2/lat/41.2974/lon/2.0833/dist/120"
ISS = "https://api.wheretheiss.at/v1/satellites/25544"

HERE = os.path.dirname(os.path.abspath(__file__))
RADAR = os.path.join(HERE, "radar.html")


def http_radar(conn):
    try:
        body = open(RADAR, "rb").read()
    except Exception:
        body = b"radar.html no encontrado"
    head = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Cache-Control: no-store\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    conn.sendall(head + body)
    conn.close()
lock = threading.Lock()
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
    path = head.split("\r\n", 1)[0]
    if "Upgrade: websocket" not in head and "upgrade: websocket" not in head.lower():
        if "GET / " in path or "GET /radar.html" in path or path.startswith("GET / "):
            http_radar(conn)
            return False
        if path.startswith("GET /"):
            http_radar(conn)
            return False
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
