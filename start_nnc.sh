#!/usr/bin/env bash
# Arranca NNC (dashboard :8080, REST :8010). No toca AGs-Core :8000.
set -e
D=/workspace/agsgpt/NNC; S=$D/NNC/sistema-nnc-ags-core-corregido-1.0.0/nnc_system; PY=$D/.venv/bin/python
cd "$S"
for n in dashboard service; do f=$D/$n.pid; [ -f $f ] && kill -0 $(cat $f) 2>/dev/null && { echo "$n ya activo"; continue; }
 if [ $n = dashboard ]; then PORT=8080 nohup $PY dashboard_server.py >$D/logs/dashboard.log 2>&1 & 
 else NNC_API_TOKEN="$(cat $D/.nnc_token)" NNC_PORT=8010 nohup $PY service_server.py >$D/logs/service.log 2>&1 & fi
 echo $! > $f; done
