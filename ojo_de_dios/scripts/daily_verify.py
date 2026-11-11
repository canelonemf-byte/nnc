#!/usr/bin/env python3
"""
Daily verification for Ojo de Dios. Usage:
  cd ojo_de_dios && .venv/bin/python scripts/daily_verify.py
Writes data/runs/daily_<stamp>.json (never overwrites history) + data/daily_verif_latest.json,
compares with data/state/daily_state.json and only flags NEW alerts (dedup by key).
Starts its own uvicorn on a free port and stops only that PID.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")
MADRID = ZoneInfo("Europe/Madrid")
RUNS = ROOT / "data" / "runs"
STATE = ROOT / "data" / "state" / "daily_state.json"
RUNS.mkdir(parents=True, exist_ok=True)
STATE.parent.mkdir(parents=True, exist_ok=True)
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def now() -> str:
    return datetime.now(MADRID).isoformat(timespec="seconds")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run_pytest() -> dict:
    cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    r = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=600)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return {"cmd": " ".join(cmd), "exit_code": r.returncode, "ok": r.returncode == 0,
            "summary": lines[-1] if lines else "", "failures": [ln for ln in lines if ln.startswith("FAILED")]}


def check(name, cond) -> dict:
    return {"check": name, "ok": bool(cond)}


def smoke(port: int) -> list[dict]:
    b = f"http://127.0.0.1:{port}/api/v1"
    c = httpx.Client(timeout=90)
    out = []

    def call(method, path, expect=200, checks=lambda j: [], **kw):
        t0 = now()
        try:
            r = c.request(method, b + path, **kw)
            j = r.json()
            cs = checks(j) if r.status_code == expect else []
            ok = r.status_code == expect and all(x["ok"] for x in cs)
            out.append({"method": method, "path": path, "t_madrid": t0, "http_status": r.status_code,
                        "expected": expect, "checks": cs, "ok": ok})
            return j
        except Exception as e:  # noqa: BLE001
            out.append({"method": method, "path": path, "t_madrid": t0, "http_status": f"error:{type(e).__name__}",
                        "expected": expect, "ok": False, "error": str(e)[:200]})
            return {}

    call("GET", "/status", checks=lambda j: [check("coord_pendiente", j["estacion"]["coord_status"] == "PENDIENTE_DE_VERIFICACION"),
                                             check("lora_sin_hw", j["ags_lora"]["hardware"] is False)])
    call("POST", "/audit/ecef", json={"lat_deg": 0, "lon_deg": 0, "h_m": 0},
         checks=lambda j: [check("x_eq_a", abs(j["ecef"]["x_m"] - 6378137.0) < 1e-3), check("sha256", len(j["input_sha256"]) == 64)])
    call("POST", "/audit/ecef", expect=422, json={"lat_deg": 91, "lon_deg": 0})
    call("GET", "/radar", checks=lambda j: [check("aircraft_list", isinstance(j.get("aircraft"), list))])
    call("GET", "/meteo", checks=lambda j: [check("fuente", bool(j.get("fuente")))])
    call("GET", "/tle/pass", params={"norad": 25544, "hours": 36},
         checks=lambda j: [check("pases_clasificados", all(p["clase"] in ("solo_geometrico", "potencialmente_visible_optico") for p in j["pases"])),
                           check("tle_no_stale", j["tle_stale"] is False)])
    call("GET", "/adsb/crosscheck", params={"az": 90, "el": 5}, checks=lambda j: [check("matches_list", isinstance(j.get("matches"), list))])
    call("POST", "/hypotheses/check", json={"id": "sim", "az_deg": 42, "el_deg": 55, "modo": "simulacion"},
         checks=lambda j: [check("no_anomaly", j["anomaly_claim"] is False), check("e_cap", j["evidencia"] == "E2"),
                           check("insuf", j["resultado"] == "no_identificado_insuficiente")])
    call("POST", "/hypotheses/check", expect=422, json={"az_deg": 1, "el_deg": 1, "origen": "observacion_optica", "force_h1": True})
    call("POST", "/hypotheses/check", expect=422, json={"az_deg": 400, "el_deg": 1})
    return out


def main() -> int:
    stamp = datetime.now(MADRID).strftime("%Y%m%dT%H%M%S")
    rep: dict = {"run_at_madrid": now(), "pytest": run_pytest()}
    port = free_port()
    log = open(RUNS / f"uvicorn_{stamp}.log", "w")
    srv = subprocess.Popen([PY, "-m", "uvicorn", "ojo_de_dios.api:app", "--host", "127.0.0.1", "--port", str(port)],
                           cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try:
                httpx.get(f"http://127.0.0.1:{port}/api/v1/status", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        rep["server"] = {"port": port, "pid": srv.pid}
        rep["endpoints"] = smoke(port)
    finally:
        srv.send_signal(signal.SIGTERM)  # only our own PID
        srv.wait(timeout=10)
    rep["endpoints_all_ok"] = all(e["ok"] for e in rep["endpoints"])
    lc = subprocess.run([PY, "scripts/live_cycle.py"], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=600)
    rep["live_cycle"] = {"exit_code": lc.returncode, "ok": lc.returncode == 0, "stderr_tail": lc.stderr[-500:]}
    cyc = json.loads((ROOT / "data" / "live_cycle_result.json").read_text()) if lc.returncode == 0 else {}
    apis = [{k: r.get(k) for k in ("api", "ok", "http_status", "fuente", "time_madrid")} for r in cyc.get("live_api_table", [])]
    rep["apis"] = apis
    passes = (cyc.get("iss_pass") or {}).get("pases") or []
    rep["iss_pases"] = passes
    vis = [p for p in passes if p["clase"] == "potencialmente_visible_optico"]
    rep["iss_visible_optico"] = vis
    rep["iss_solo_geometrico_count"] = len(passes) - len(vis)
    rep["detecciones_resumen"] = [{k: d.get(k) for k in ("id", "origen", "excluido_por", "resultado", "evidencia")} for d in cyc.get("detecciones", [])]

    prev = json.loads(STATE.read_text()) if STATE.exists() else {"alert_keys": [], "apis": {}}
    cur_api = {a["api"]: a["ok"] for a in apis}
    changes = [{"api": k, "antes": prev["apis"].get(k), "ahora": v} for k, v in cur_api.items() if prev["apis"].get(k) is not None and prev["apis"].get(k) != v]
    keys = []
    if not rep["pytest"]["ok"]:
        keys.append("pytest_fail:" + rep["pytest"]["summary"])
    if not rep["endpoints_all_ok"]:
        keys.append("endpoint_fail:" + ",".join(e["path"] for e in rep["endpoints"] if not e["ok"]))
    keys += [f"api_change:{c['api']}:{c['ahora']}" for c in changes]
    keys += [f"iss_visible:{p['visible_start_utc'][:16]}" for p in vis]
    new = [k for k in keys if k not in set(prev["alert_keys"])]
    rep["comparacion"] = {"estado_previo": str(STATE), "api_changes": changes, "alert_keys": keys, "alertas_nuevas": new}
    rep["wake_parent"] = bool(new)
    out = RUNS / f"daily_{stamp}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2))
    (ROOT / "data" / "daily_verif_latest.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2))
    STATE.write_text(json.dumps({"updated_madrid": now(), "apis": cur_api,
                                 "alert_keys": sorted(set(prev["alert_keys"]) | set(keys))[-200:]}, ensure_ascii=False, indent=2))
    print(json.dumps({"file": str(out), "pytest": rep["pytest"]["summary"], "endpoints_all_ok": rep["endpoints_all_ok"],
                      "visibles": len(vis), "alertas_nuevas": new}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
