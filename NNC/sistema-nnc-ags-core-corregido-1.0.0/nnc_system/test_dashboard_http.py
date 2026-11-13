"""Pruebas del dashboard NNC: bind por defecto, /health JSON y 404 en rutas desconocidas."""
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import dashboard_server as ds


def test_dashboard_bind_host_default(monkeypatch):
    monkeypatch.delenv("NNC_DASHBOARD_HOST", raising=False)
    assert ds.dashboard_bind_host() == "127.0.0.1"


def test_dashboard_bind_host_configurable(monkeypatch):
    monkeypatch.setenv("NNC_DASHBOARD_HOST", "0.0.0.0")
    assert ds.dashboard_bind_host() == "0.0.0.0"
    monkeypatch.setenv("NNC_DASHBOARD_HOST", "  ")
    assert ds.dashboard_bind_host() == "127.0.0.1"


@pytest.fixture(scope="module")
def dashboard_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ds.DashboardHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.headers.get_content_type(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get_content_type(), e.read()


def test_health_json(dashboard_server):
    status, ctype, body = _get(dashboard_server + "/health")
    assert status == 200
    assert ctype == "application/json"
    data = json.loads(body.decode("utf-8"))
    assert data["status"] == "ok" and data["service"] == "nnc-dashboard"


def test_root_html(dashboard_server):
    status, ctype, body = _get(dashboard_server + "/")
    assert status == 200
    assert "html" in ctype
    assert b"NNC Dashboard" in body


def test_unknown_path_404(dashboard_server):
    status, ctype, body = _get(dashboard_server + "/this-does-not-exist")
    assert status == 404
    assert ctype == "application/json"
    assert json.loads(body.decode("utf-8"))["error"] == "not_found"
