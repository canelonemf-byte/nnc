#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker no está instalado; no se ha desplegado nada." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: se requiere el complemento Docker Compose v2." >&2
  exit 1
fi
if [ ! -f .env ]; then
  if ! command -v openssl >/dev/null 2>&1; then
    echo "ERROR: instala openssl o crea nnc_system/.env con NNC_API_TOKEN." >&2
    exit 1
  fi
  printf 'NNC_API_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
  chmod 600 .env
  echo "Se creó .env con un token aleatorio. No lo publiques ni lo compartas."
fi
if ! grep -Eq '^NNC_API_TOKEN=.{32,}$' .env || grep -q 'CAMBIAR_ESTE_VALOR' .env; then
  echo "ERROR: NNC_API_TOKEN debe tener al menos 32 caracteres en .env." >&2
  exit 1
fi

docker compose config >/dev/null
docker compose up --build -d
echo "Esperando comprobación de salud..."
for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    echo "API saludable: http://127.0.0.1:8000/health"
    echo "Panel: http://127.0.0.1:8080"
    echo "Los conectores externos no están conectados; telemetría de demostración únicamente."
    exit 0
  fi
  sleep 2
done
echo "ERROR: la API no superó la comprobación de salud. Logs:" >&2
docker compose logs --tail=100 >&2
exit 1
