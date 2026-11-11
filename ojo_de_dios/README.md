# Ojo de Dios / NNC Consola v2 — software de exclusión (solo software)

**Estado:** prototipo de software. No hay cámaras duales, GNSS/PPS, NTP verificado, espectrómetro ni radio LoRa.
AGs-Core/LoRa = **solo esquema JSON/binario**, sin integración ni pruebas de radio.

## Uso
```bash
cd /workspace/ojo_de_dios
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # si no existe .venv
PYTHONPATH=src .venv/bin/python -m pytest -q                          # tests (offline salvo test_api radar/meteo)
PYTHONPATH=src .venv/bin/uvicorn ojo_de_dios.api:app --host 127.0.0.1 --port <puerto_libre>
PYTHONPATH=src .venv/bin/python scripts/live_cycle.py                 # ciclo con APIs reales
.venv/bin/python scripts/daily_verify.py                              # tests + servidor propio + smoke + ciclo + comparación
```
`daily_verify.py` arranca uvicorn en un puerto libre y solo detiene **su propio PID**. Escribe
`data/runs/daily_<stamp>.json`, `data/runs/live_cycle_<stamp>.json` (histórico, no se sobrescribe),
copias `data/*_latest`/`live_cycle_result.json`, y `data/state/daily_state.json` (alertas ya emitidas → no repite).

## Endpoints `/api/v1`
`status`, `audit/ecef` (POST; h_m = altura **elipsoidal** WGS84), `radar`, `hypotheses/check` (POST),
`meteo`, `tle/pass` (pases geométricos + clasificación óptica), `adsb/crosscheck`. Entradas inválidas → 422.

## Visibilidad ISS
Muestreo cada 10 s de cada pase con el ≥10°: **potencialmente_visible_optico** solo si a la vez satélite
iluminado (`is_sunlit`, de421) y Sol ≤ −6° en el observador. Si no: **solo_geometrico** (+motivo).
La meteo es pronóstico de modelo → siempre "incertidumbre_meteo". No se calcula magnitud: no hay "más brillante/mejor".
Pases a >2 días del epoch TLE → `confianza_orbita: reducida`.

## Árbol de hipótesis
Tri-estado True / False / `indeterminado` (desconocido ≠ falso). Orden H0..H7; primera True excluye.
Un frame/una cámara no prueba H0; ausencia de ADS-B no descarta aeronave; ADS-B en vivo solo se cruza con
detecciones contemporáneas (sin histórico). `force_h1/h2` solo en simulación/sintética, nunca producción.
H_kin = bandera (requiere cámaras duales + sync + distancias y errores, criterio a−3σ > 50 g); nunca excluye ni
establece origen exótico. H_mat sin sensor = indeterminado.

## Evidencia
simulacion / sintetica_desde_catalogo → E2 máx. Óptica sin sync → E1. Óptica + sync (config GNSS/NTP + `t_sync`) → E3;
E4+ requiere cámaras duales coincidentes. Los flags de hardware son declaraciones de configuración, **no prueba**.

## Limitaciones
- Coordenadas aproximadas del centro de El Prat (PENDIENTE_DE_VERIFICACION); ondulación geoide 49 m aprox.
- ADS-B: `alt_geom` preferido; si solo hay `alt_baro` se marca barométrica (error de cientos de ft posible).
- OpenSky da error de conexión TLS desde esta máquina; airplanes.live 403 (requiere contacto). Fallback efectivo: adsb.lol.
- H2 solo comprueba el NORAD indicado (por defecto ISS); H3 sin catálogo estelar.
- Umbrales iniciales sin calibrar con datos de campo.
