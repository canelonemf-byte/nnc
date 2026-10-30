# Ojo de Dios / NNC Consola v2

Sky-object exclusion API for a station near El Prat de Llobregat.

## Run API

```bash
cd /workspace/ojo_de_dios
. .venv/bin/activate
PYTHONPATH=src uvicorn ojo_de_dios.api:app --host 127.0.0.1 --port 8080
```

## Live cycle

```bash
PYTHONPATH=src python scripts/live_cycle.py
```

## Tests

```bash
PYTHONPATH=src pytest -q
```

Station coordinates are **PENDIENTE DE VERIFICACION** (approx town centre).
AGs-Core+LoRa is schema-only (no radio hardware).
