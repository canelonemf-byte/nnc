"""Ejecuta tests_deploy.py (handler Vercel /api/live con CORS, sin red) dentro de pytest.

Autoría: Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia de IA. Licencia: MIT.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deploy_cors_y_estructura_api_live():
    r = subprocess.run([sys.executable, str(ROOT / "tests_deploy.py")], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "OK tests_deploy" in r.stdout
