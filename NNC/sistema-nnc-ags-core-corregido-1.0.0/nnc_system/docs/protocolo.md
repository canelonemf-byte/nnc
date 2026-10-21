### Control NNC (no cooperativo) — Prat de Llobregat
#### Qué es esto
Filtro y ficha de caso para objetos aéreos  **sin baliza** . No es un detector de FANI. Estados permitidos: explicado, datos insuficientes, cinemática no cerrada, dentro de envolvente, candidato cinemático, material no medido, residuo.
#### Regla de oro
Velocidad real ≈ velocidad angular × distancia. Sin distancia no se afirma km/h imposibles ni materiales desconocidos.
#### No abrir un caso cuando
OpenSky no lista aviones. Eso es silencio de red, no un objeto.
#### Abrir un caso cuando
Hay foto/vídeo calibrable, radar con distancia, o informe con hora UTC y al menos un dato angular.
#### Orden de exclusión
H0 cobertura → H1 ADS-B → H2 OGN → H3 satélite → H4 globo (Sondehub) → H5 meteo → H6 artefacto → H7 animal → cinemática → material.
H7 animal: |v|>110 m/s o jet/LEO ⇒ DESCARTADO. |v|≤35 m/s y cerca ⇒ COMPATIBLE con ave (no afirmado). Sin v ⇒ no se decide.
#### Código implementado
correccion_errores.py: Hamming(7,4), CRC-16, Kalman, cinemática, triangulación, procesar_traza. Unitarias: resultados_correccion_errores.json (16/16). Simulación: ficha_caso.simulacion_*.json. ISS y EZY95FN: animal DESCARTADO. OGN: ogn_prat.json. Meteo: meteo_prat.json. Globos: globos_sondehub.json.
#### Ordenador cuántico
No hay QPU ni Qiskit en este nodo. El código de 3 bits es una simulación clásica (voto por mayoría). No se inventa un resultado cuántico.
#### Ingreso ECEF (2026-10-02)
ingreso_ecef.py y la app build-beta/index.html aplican el mismo filtro. Rechazo duro: h < 0, G declarada sin v1/v2/Δt, G que no cierra, Mach > 5 con firma térmica falsa. Fuera de Madrid r = 200 km es bandera, no se mezcla con Prat. Flash, malla y psi no son sensor. anomalous_node_01: RECHAZADO_INGRESO, E0. Inverso: 41.40613123° N, 1.98075011° E, h = −6116.66 m.
#### Ojo dios (2026-10-03)
GodMode smol-ai latest resuelve a v1.0.0-beta.10 (commit 8ac3ffd, 2023-11-17). Es un navegador Electron de chats, no un sensor. Binario no instalado. Procedencia: godmode_provenance.json. La beta tiene modo Ojo dios: compara fixture y sintético a la vez.
