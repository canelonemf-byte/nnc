# Auditoría de correcciones NNC + AGs-Core — 2026-10-20

## Cambios aplicados

- Reparado `upload_nnc_project_to_github.py`: sintaxis, rutas portables y exclusión explícita de binarios no soportados por el flujo de Contents API.
- Corregidas conversiones WGS84 y validación de coordenadas finitas; añadidas pruebas en ecuador y Barcelona.
- Corregida triangulación ENU: validación de entradas, geometría de rayos y `gap_m` desconocido como `null` JSON (Python `None`), nunca como un valor de error artificial.
- Corregida la entropía de Shannon con probabilidades normalizadas.
- Mejorada la inicialización del EKF y la actualización de covarianza con forma de Joseph.
- Eliminada la inferencia incorrecta de carga g a partir de velocidad. Solo se calcula cuando se proporciona aceleración en m/s²; los escenarios sin medición informan valor desconocido.
- Cambiada la salida de los módulos de sensores: telemetría sintética etiquetada como simulada, sin fingir cobertura, streaming, integridad ni pérdida de paquetes medidos.
- Cambiados los informes de calibración y mapas de calor para indicar datos sintéticos y no validados.
- Añadida API REST de demostración con `/health`, `/api/status` y `POST /api/audit`; el endpoint de auditoría requiere token configurado y devuelve 401 sin autorización.
- Añadido panel HTTP con rutas de recursos limitadas a `assets/` y estado de conectores explícitamente desconectados.
- Sustituido el despliegue Docker heredado que anunciaba servidores gRPC/TLS inexistentes por un Compose de API REST y panel, con usuario sin privilegios, puertos enlazados a localhost, token obligatorio y healthcheck.
- Corregido `deploy.sh` para no fabricar certificados mTLS ni afirmar que existe un servicio gRPC.
- Actualizada la documentación y retiradas cachés compiladas y el ZIP anidado antiguo.

## Verificaciones ejecutadas en este entorno

- `python -m compileall -q -f .`: PASS.
- Análisis sintáctico de `nnc_system/deploy.sh` con `bash -n`: PASS.
- Parseo de todos los JSON: PASS.
- Parseo YAML de `docker-compose.yml`: PASS.
- `python main.py` (runtime raíz): PASS; el resultado se etiqueta como demostración.
- `python nnc_system/main.py`: PASS; indica correctamente que no hay certificados TLS operativos.
- `python nnc_system/suite_autotest_calibracion_maestra.py`: 7/7 pruebas PASS.
- Smoke test HTTP real en procesos locales: API `/health` 200; panel `/api/status` 200; auditoría sin token 401; auditoría con token válido 200; sin exposición del archivo de configuración.
- Scripts finitos de simulación y generación: todos terminaron con código 0 en este entorno.

## Límites pendientes, declarados expresamente

- Docker/Podman no están instalados en el entorno de revisión. Por tanto, no se ha podido construir la imagen ni ejecutar `docker compose up`; el despliegue en contenedores sigue pendiente de comprobación en un host con Docker.
- No se ha implementado un servidor gRPC real, TLS/mTLS, JWT, limitación de tasa, allowlist de IP ni conexión a proveedores satelitales. Esta versión no los anuncia como operativos.
- Las pruebas de geometría utilizan datos sintéticos controlados. No constituyen calibración física, evidencia de eventos reales ni validación experimental.
- El panel usa CDN externos para algunos recursos gráficos; estos recursos requieren conectividad del navegador.
- Los informes PDF heredados se conservan como documentación histórica y no son evidencia de validación de esta versión.

## Estado final

**Verificado localmente para ejecución Python, suite de pruebas y API/panel HTTP de demostración. No declarar producción, validación física ni despliegue Docker completado hasta ejecutar las pruebas pendientes en el entorno destino.**
