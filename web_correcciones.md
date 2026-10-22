# Correcciones para las webs NNC y posts de X
Autoría: Lázaro López Paz con asistencia de IA · Software MIT · Documentos CC BY 4.0
Webs: https://quartz-trail-summit-turbo.grok.me y https://drift-hazel-urban-dawn.grok.me
(Solo el usuario puede editarlas. Nada de esto se ha publicado.)

## 1. Aviso para pegar arriba del todo en AMBAS webs (HTML)
```html
<div style="background:#3a2a00;color:#ffd;border:2px solid #fc6;padding:10px;font-family:sans-serif;margin:8px 0">
  <strong>⚠ Aviso:</strong> esta página es una <strong>demostración</strong>. Las posiciones, trayectorias,
  anomalías, mapa de calor, índice Kp y alertas que se muestran son <strong>DATOS SIMULADOS</strong>,
  no observaciones en tiempo real.<br>
  <strong>Nivel de evidencia:</strong> software E3 (funciona y tiene pruebas); <strong>detección de anomalías E1</strong>
  (hipótesis, sin validación con datos reales ni revisión externa). No hay ningún resultado E4–E6.<br>
  Autoría: Lázaro López Paz con asistencia de IA · Código MIT · Textos CC BY 4.0.
</div>
```
Además: sustituir cualquier insignia “E3”, “E6” o “validado” referida a la detección por **“Detección E1 (no validada)”**,
y cambiar textos tipo “LIVE / EN VIVO / tiempo real” por “DEMO SIMULADA”.

## 2. Qué es REAL ya en el sistema NNC local (no en las webs)
Desde el 2026-10-22 el NNC local (dashboard :8080 y API :8010, endpoint `/api/live`) lee, con fuente y hora:
- OpenSky Network REST (ADS-B, bbox 40.8–41.8N / 1.5–2.7E) — REAL, uso no comercial, atribución obligatoria.
- Posición ISS — wheretheiss.at — REAL.
- MET Norway Locationforecast — REAL pero es PREVISIÓN de modelo (CC BY 4.0, atribución).
- NOAA SWPC índice Kp planetario — REAL.
Esto NO eleva la detección: sigue en E1.

## 3. Cómo conectar las webs a datos reales (opciones honestas)
Las webs grok.me son páginas estáticas alojadas fuera de este ordenador; no pueden leer el NNC local (127.0.0.1).
- **Opción A (más simple):** mantener la web como demo con el aviso del punto 1.
- **Opción B (datos reales en el navegador):** añadir JavaScript que llame directamente desde el navegador del visitante a
  `https://api.wheretheiss.at/v1/satellites/25544` (permite CORS) y mostrar fuente + hora. OpenSky y MET Norway pueden
  bloquear llamadas del navegador (CORS / User-Agent obligatorio en MET) — PENDIENTE DE VERIFICACIÓN por fuente.
- **Opción C (completa):** publicar el NNC (`/api/live`) en un servidor propio con HTTPS (p.ej. Vercel/servidor con proxy)
  y que la web lea de ahí. Requiere tu decisión y cuenta; respetar términos de OpenSky (no comercial) y atribuciones.
Fragmento para la opción B:
```html
<div id="iss-real">ISS: cargando…</div>
<script>
fetch('https://api.wheretheiss.at/v1/satellites/25544').then(r=>r.json()).then(d=>{
 document.getElementById('iss-real').textContent='ISS (REAL, fuente wheretheiss.at, '+
 new Date(d.timestamp*1000).toISOString()+'): '+d.latitude.toFixed(2)+', '+d.longitude.toFixed(2)+', '+d.altitude.toFixed(0)+' km';
}).catch(e=>{document.getElementById('iss-real').textContent='ISS: sin datos (no se simula)';});
</script>
```

## 4. Borradores de posts de X (NO publicados)
**Post NNC Consola:**
> NNC Consola: demo de un sistema de vigilancia de anomalías aéreas en El Prat (Barcelona). La interfaz usa datos SIMULADOS; la detección está en nivel E1 (hipótesis, sin validar). Versión local ya lee datos públicos reales (OpenSky, ISS, MET Norway, NOAA). Por Lázaro López Paz con asistencia de IA. Código MIT.

**Post Control del espacio aéreo:**
> Control del espacio aéreo (demo): visualización con datos SIMULADOS, no tráfico en vivo. Detección de anomalías en nivel E1, sin validación externa. Siguiente paso: conectar datos ADS-B reales con atribución a OpenSky Network. Lázaro López Paz, con asistencia de IA.

## Servidor NNC desplegado (opción C) — 2026-10-22 23:53 CEST
- URL de producción: https://nnc-live-lazaro-lopez-paz.vercel.app (`/health`, `/api/live`), proyecto Vercel `nnc-live`, equipo `lazaro-lopez-paz`, Vercel Authentication desactivada (público por diseño).
- CORS: solo https://quartz-trail-summit-turbo.grok.me y https://drift-hazel-urban-dawn.grok.me (`Vary: Origin`).
- Verificado 23:53 CEST: ISS, MET Norway (previsión) y NOAA Kp = REAL/OK.
- OpenSky desde la nube: PENDIENTE (timeout desde Vercel iad1). Requiere credenciales OpenSky del usuario o servidor no-cloud. El snippet lo muestra como PENDIENTE; no se simula.
- `web_snippet_live.html` ya incluye `NNC_SERVER`; pegar el snippet completo en ambas webs.
