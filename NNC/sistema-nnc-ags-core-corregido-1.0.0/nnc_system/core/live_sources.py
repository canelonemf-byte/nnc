"""Conectores a fuentes públicas REALES sin clave (stdlib). Autoría: Lázaro López Paz con asistencia de IA. MIT.
Cada lectura incluye fuente, URL, hora de obtención y etiqueta REAL. Si falla: estado PENDIENTE/ERROR, nunca se simula.
Nivel de evidencia de detección: E1 (ingerir datos reales no valida la detección)."""
import json, time, threading, urllib.request

UA = "NNC-LLP/1.0 (Lazaro Lopez Paz; proyecto NNC no comercial)"
LAT, LON = 41.30, 2.08  # El Prat de Llobregat
BBOX = dict(lamin=40.8, lomin=1.5, lamax=41.8, lomax=2.7)
SOURCES = {
    "opensky": ("OpenSky Network (ADS-B, uso no comercial, atribución requerida)",
                "https://opensky-network.org/api/states/all?lamin={lamin}&lomin={lomin}&lamax={lamax}&lomax={lomax}".format(**BBOX)),
    "iss": ("wheretheiss.at", "https://api.wheretheiss.at/v1/satellites/25544"),
    "met": ("MET Norway Locationforecast 2.0 (CC BY 4.0)",
            f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LAT}&lon={LON}"),
    "kp": ("NOAA SWPC planetary K-index", "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"),
}
EVIDENCIA = "E1 (detección no validada; datos de entrada reales)"

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def parse_opensky(d):
    st = d.get("states") or []
    ac = [{"icao24": s[0], "callsign": (s[1] or "").strip(), "pais": s[2], "lon": s[5], "lat": s[6],
           "alt_baro_m": s[7], "en_tierra": s[8], "vel_m_s": s[9], "rumbo": s[10]} for s in st]
    return {"t_fuente_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d.get("time", 0))),
            "n_aeronaves": len(ac), "aeronaves": ac}

def parse_iss(d):
    return {"t_fuente_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d["timestamp"])),
            "lat": d["latitude"], "lon": d["longitude"], "alt_km": d["altitude"], "vel_km_h": d["velocity"]}

def parse_met(d):
    p = d["properties"]; ts = p["timeseries"][0]
    return {"t_fuente_utc": p["meta"]["updated_at"], "t_prevision_utc": ts["time"],
            "nota": "PREVISIÓN de modelo, no observación", **ts["data"]["instant"]["details"]}

def parse_kp(d):
    if isinstance(d[0], list):  # formato antiguo con cabecera
        hdr, row = d[0], d[-1]; r = dict(zip(hdr, row))
    else:
        r = d[-1]
    return {"t_fuente_utc": r.get("time_tag"), "kp": float(r.get("Kp", r.get("kp_index", "nan")))}

PARSERS = {"opensky": parse_opensky, "iss": parse_iss, "met": parse_met, "kp": parse_kp}

def read_source(key, fetch=fetch_json):
    name, url = SOURCES[key]
    base = {"fuente": name, "url": url, "obtenido_utc": _now()}
    try:
        return {**base, "tipo": "REAL", "estado": "OK", "datos": PARSERS[key](fetch(url))}
    except Exception as e:
        return {**base, "tipo": "SIN_DATOS", "estado": "PENDIENTE", "error": f"{type(e).__name__}: {e}"[:200]}

_cache, _lock = {}, threading.Lock()
TTL = {"opensky": 15, "iss": 5, "met": 600, "kp": 600}

def snapshot(fetch=fetch_json):
    out = {}
    for k in SOURCES:
        with _lock:
            c = _cache.get(k)
        if not c or time.time() - c[0] > TTL[k]:
            c = (time.time(), read_source(k, fetch))
            with _lock: _cache[k] = c
        out[k] = c[1]
    return {"generado_utc": _now(), "evidencia_deteccion": EVIDENCIA,
            "autoria": "Lázaro López Paz con asistencia de IA", "fuentes": out}
