# Sistema NNC + AGs-Core — versión corregida 1.0.0

Plataforma de demostración para auditoría de eventos, geometría ECEF/ENU, cálculos cinemáticos y un panel web. **La telemetría satelital incluida es sintética**: esta distribución no incluye conectores activos a ADS-B, NORAD/CelesTrak, NOAA/SWPC ni servicios multiespectrales. No debe usarse como sistema de vigilancia validado ni como instrumento científico sin datos, calibración y validación independientes.

## Requisitos

- Python 3.10 o posterior (probado en Python 3.13).
- NumPy: `python -m pip install -r nnc_system/requirements.txt`.
- Docker/Compose solo para el despliegue en contenedores. Docker no es necesario para las pruebas locales.

## Ejecutar y comprobar en local

```bash
python -m pip install -r nnc_system/requirements.txt
cd nnc_system
python suite_autotest_calibracion_maestra.py
python main.py
```

La suite verifica conversiones WGS84, triangulación sintética, entropía, EKF, CRC, HMAC y el etiquetado de datos simulados. Un resultado PASS valida únicamente esos casos de software; no equivale a calibración física ni a validación de fuentes externas.

## API REST

La API expone `GET /health`, `GET /api/status` y `POST /api/audit`. El endpoint de auditoría exige un token configurado por variable de entorno. Ejemplo local: 

```bash
# Linux/macOS; usa un secreto aleatorio propio, no el ejemplo
export NNC_API_TOKEN="REEMPLAZAR_POR_UN_SECRETO_ALEATORIO_LARGO"
cd nnc_system
python service_server.py
```

En otra terminal, `curl http://127.0.0.1:8000/health`. Para auditar, envía un JSON a `POST /api/audit` con cabecera `Authorization: Bearer $NNC_API_TOKEN`. La API local no proporciona TLS por sí sola; mantenla en localhost o detrás de un proxy TLS correctamente configurado.

## Panel

```bash
cd nnc_system
python dashboard_server.py
```

Abrir `http://127.0.0.1:8080`. El panel es visualización de demostración; los estados de conectores se marcan como no conectados.

## Docker Compose

1. Instala Docker Engine y el complemento Docker Compose.
2. En `nnc_system/`, crea un archivo `.env` con `NNC_API_TOKEN=` seguido de un secreto aleatorio largo. No lo publiques.
3. Ejecuta `docker compose config`, después `docker compose up --build -d`.
4. Comprueba `docker compose ps`, `docker compose logs --tail=100` y `curl http://127.0.0.1:8000/health`.
5. Para detener: `docker compose down`. Los puertos se enlazan a `127.0.0.1`, no a todas las interfaces.

## Límites y seguridad

- La API REST de esta versión es HTTP; no afirma tener TLS/mTLS. Usa un proxy inverso TLS en despliegues remotos.
- La clave de `NNC_API_TOKEN` debe ser secreta, larga y distinta de cualquier valor de ejemplo.
- El módulo HMAC de demostración no es JWT ni sustituye un proveedor de identidad.
- Los datos de telemetría sintética están etiquetados como no reales y no validados.
- La triangulación requiere que las posiciones estén en un mismo marco ENU local, en metros; las entradas ECEF no se convierten automáticamente a ENU.
- La aceleración en g solo se informa si se proporciona `aceleracion_m_s2`; no se deduce de la velocidad.
- Docker debe probarse en un host con Docker instalado. Si no está disponible, la prueba local no acredita el arranque de contenedores.

## Estructura

- `core/`: implementación ligera del controlador raíz.
- `nnc_system/core/`: control multidominio, geometría, filtro EKF, seguridad y telemetría sintética.
- `nnc_system/service_server.py`: API REST de demostración.
- `nnc_system/dashboard_server.py`: panel web.
- `nnc_system/suite_autotest_calibracion_maestra.py`: pruebas automatizadas reproducibles.
- `nnc_system/docker-compose.yml`, `Dockerfile`: despliegue de API y panel.
