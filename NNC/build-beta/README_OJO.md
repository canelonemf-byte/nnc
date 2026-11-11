# NNC Build Beta + vista "Ojo de Dios"

Autoría: Lázaro López Paz, El Prat de Llobregat, Barcelona, España, con asistencia IA.

## Arranque
```bash
# desde la raíz del repo nnc
pip install -r ojo_de_dios/requirements.txt
cd NNC/build-beta
NNC_WS_PORT=8765 python ws_vivo.py
# abrir http://127.0.0.1:8765/#ojo   (radar: /radar.html · ingreso ECEF: /index.html)
```
El módulo se busca en `OJO_DE_DIOS_SRC` (si se define), luego en `<repo>/ojo_de_dios/src` y luego en `../ojo_de_dios/src`.
Sin httpx/skyfield, `/api/ojo` responde 503 y el radar sigue funcionando.
Cabecera del radar: servido por `ws_vivo.py` muestra datos en vivo por WebSocket; abierto como `file://` o si el WS falla,
muestra la instantánea rotulada "INSTANTÁNEA HISTÓRICA 2026-10-04 (no en vivo)". En la pestaña Ojo de Dios la cabecera muestra los datos en vivo de la vista.

## Endpoints (solo GET)
- `/api/ojo?radio_km=&alt_min_ft=&alt_max_ft=&el_min_deg=&edad_max_s=` → vista completa (JSON). Entradas inválidas → 422.
- `/api/ojo/historial?n=50` → últimas líneas de `data/historial_ojo.jsonl`.
- `/api/ojo/salud` · `/ws/flujo` (WebSocket, formato sin cambios).

## Reglas aplicadas
- Procesos reutilizados de `ojo_de_dios`: `adsb.get_adsb` (adsb.lol→OpenSky→airplanes.live), `tle.predict_pass` + `visibility.classify_passes`, `meteo.get_meteo` (Open-Meteo→MET Norway→caché), `hypotheses.evaluate_detection` (H0–H7 + H_kin + H_mat).
- Aviones ADS-B y la ISS pasan por la cadena con `origen=sintetica_desde_catalogo` → tope **E2**. Estados: `EXPLICADO` | `no_explicado_pendiente` | `indeterminado`. **Nunca FANI.**
- Detecciones ópticas: solo si existe `data/detecciones_opticas.jsonl` con `origen=observacion_optica` (cámara real). Si no, la vista dice "sin detecciones ópticas reales".
- Aviso solo con desviación medible: residuo > 3σ entre predicción y medida (aviones: estima entre snapshots; ISS: SGP4 Celestrak vs wheretheiss.at).
- Silencio ADS-B = `indeterminado`, sin aviso.
- ω se calcula entre snapshots; R = "" y v = "" porque no hay distancia medida por la estación (la distancia de baliza no es R medida).
- Umbrales y σ: PENDIENTE_DE_VERIFICACION. Coordenadas de estación: aproximadas (PENDIENTE_DE_VERIFICACION).

## Tests
```bash
# desde la raíz del repo (pytest.ini incluye ojo_de_dios/tests y NNC/build-beta/tests)
python -m pytest -q -p no:cacheprovider
```
