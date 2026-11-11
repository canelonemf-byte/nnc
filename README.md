# nnc

Proyecto nnc

## Autoría

- **Autor:** Lázaro López Paz, El Prat de Llobregat, Barcelona, España
- **ORCID:** [0000-0001-8601-1963](https://orcid.org/0000-0001-8601-1963)
- Elaborado con asistencia de inteligencia artificial
- Sin afiliaciones institucionales

## Estado

Proyecto en desarrollo / documentación. No afirmar validación experimental salvo que el código o los informes del propio repositorio lo demuestren.

## Contenido (raíz)

```
.github/workflows/ci.yml   CI: py_compile + pytest
api/                       funciones Vercel (/api/live, /health)
DESPLIEGUE.md              despliegue en Vercel
NNC/                       sistema NNC (dashboard :8080, servicio REST :8010, build-beta con vista Ojo de Dios, ver NNC/build-beta/README_OJO.md)
ojo_de_dios/               módulo Ojo de Dios (src/ + tests/, requirements.txt propio)
pytest.ini                 pythonpath ojo_de_dios/src; tests en ojo_de_dios/tests, NNC/build-beta/tests y tests/
requirements.txt           raíz: solo stdlib (funciones Vercel)
start_nnc.sh               arranque local de dashboard y servicio
tests/                     test_deploy_cors.py (ejecuta tests_deploy.py dentro de pytest)
tests_deploy.py            prueba local del handler /api/live con CORS (sin red)
vercel.json
web_correcciones.md
web_snippet_live.html
```

## Instalación

```bash
pip install -r requirements.txt                 # funciones Vercel (stdlib)
pip install -r ojo_de_dios/requirements.txt     # Ojo de Dios y pruebas
```

## Pruebas

```bash
python -m pytest -q          # Ojo de Dios + vista Ojo NNC/build-beta + CORS de /api/live (sin red)
```

## Operación local

En el equipo de trabajo NNC corre desde `/workspace/agsgpt/NNC` con su propio venv (`.venv`):
dashboard en `http://127.0.0.1:8080/` y servicio REST en `http://127.0.0.1:8010/health`
(`start_nnc.sh`; tras una restauración del equipo: `ags-core-v3.6/scripts/recuperar_todo.sh`).
Despliegue público `nnc-live.vercel.app`: devolvía 404 el 2026-11-11 (redespliegue PENDIENTE).

## Uso

Archivos Python principales (revisar cada uno antes de ejecutar):
- `NNC/build-beta/ws_vivo.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/app_dashboard_server.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/core/ags_core_lora_agents.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/core/ecef_bowring.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/core/triangulacion_enu.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/main.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system/core/advanced_math_physics.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system/core/ags_core_lora_agents.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system/core/ecef_bowring.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system/core/grafana_logger.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system/core/live_sources.py`
- `NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system/core/notifier.py`


## Licencia

Ver archivo `LICENSE` (o `LICENSE.md`) en la raíz. Documentación bajo CC BY 4.0 cuando aplique; código habitualmente MIT, salvo indicación contraria.
