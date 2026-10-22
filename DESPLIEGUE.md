# NNC · Despliegue (opciones B y C) — Lázaro López Paz con asistencia de IA
Estado: PREPARADO, NO desplegado. Nada subido. Verificado 2026-10-22 23:20 (Madrid).

## B · Snippet para pegar en las webs grok.me
Archivo: `web_snippet_live.html` (autocontenido). CORS comprobado con `Origin: https://quartz-trail-summit-turbo.grok.me`:
| Fuente | Access-Control-Allow-Origin | En navegador |
|---|---|---|
| wheretheiss.at (ISS) | `*` | REAL ✅ |
| MET Norway Locationforecast (CC BY 4.0) | `*` | REAL ✅ (previsión, no observación) |
| NOAA SWPC Kp | `*` | REAL ✅ |
| OpenSky Network | `https://opensky-network.org` | PENDIENTE ❌ → vía servidor C |
| open-notify | sin respuesta / solo http | descartado |
Nota MET Norway: sus términos piden identificación; desde navegador se envía Origin/Referer de la web. PENDIENTE DE VERIFICACIÓN de cumplimiento si el tráfico crece.
Para activar OpenSky en el snippet: poner la URL del servidor en `var NNC_SERVER = "..."`.

## C · Servidor propio — recomendado: Vercel (Hobby, gratis)
Por qué: cuenta Vercel ya conectada (usuario `canelonemf-8600`, plan **hobby**), código solo stdlib (sin dependencias), funciones Python serverless, HTTPS incluido. Hobby es solo para uso no comercial, coherente con los términos de OpenSky.
Alternativas: Render (free web service con Docker, se duerme tras inactividad), Fly.io (requiere tarjeta). Existe `NNC/.../nnc_system/Dockerfile` para ellas.

Archivos: `vercel.json`, `api/live.py`, `api/health.py`, `api/_common.py`, `requirements.txt`, `.vercelignore`, `tests_deploy.py`.
- `GET /api/live` y `GET /health`. CORS solo para los dos dominios grok.me (configurable con `NNC_ALLOWED_ORIGINS`).
- No se despliega `/api/audit`; `NNC_API_TOKEN` no hace falta. Si algún día se añade, irá como variable de entorno de Vercel, nunca en el código.

Pasos (los hace o aprueba el usuario):
1. Autorizar el acceso del conector al equipo `lazaro-lopez-paz` (ahora da 403 al listar proyectos).
2. Subir el repo a GitHub (requiere "sube") o desplegar desde archivos.
3. Crear proyecto Vercel, raíz = este repo; desplegar. Probar `https://<proyecto>.vercel.app/api/live`.
4. Poner esa URL en `NNC_SERVER` del snippet y pegarlo en las dos webs.

## Decisiones del usuario
- Aprobar cuenta/proyecto Vercel (coste 0 € en Hobby; límites del plan).
- Aceptar términos OpenSky: uso no comercial y cita (Schäfer et al., IPSN 2014).
- PENDIENTE DE VERIFICACIÓN: OpenSky puede limitar o bloquear peticiones anónimas desde IPs de nube; si ocurre, haría falta cuenta OpenSky (credenciales como variables de entorno).
- Detección sigue en E1 (no validada).
