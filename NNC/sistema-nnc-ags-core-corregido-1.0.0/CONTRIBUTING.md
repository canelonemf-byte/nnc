# Guía de Contribución — Sistema NNC + AGs-Core

¡Gracias por tu interés en contribuir al proyecto **NNC + AGs-Core**! Este repositorio alberga un sistema de demostración (E3 software, datos simulados) para validación geométrica 3D y auditoría de eventos; no es un sistema de detección operativo ni validado.

---

## 📜 Código de Conducta

Nos comprometemos a proporcionar un entorno respetuoso, colaborativo y riguroso. Se espera que todas las personas participantes mantengan un trato profesional y científico.

---

## 🛠️ Flujo de Trabajo para Contribuir

1. **Haz un Fork** del repositorio oficial en GitHub.
2. **Crea una Rama de Función (*Feature Branch*)**:
   ```bash
   git checkout -b feature/nueva-funcionalidad
   ```
3. **Escribe y Documenta tu Código**:
   - Sigue las convenciones PEP 8 para código Python.
   - Incluye pruebas unitarias para nuevos módulos en `core/`.
   - Asegúrate de no incluir claves privadas ni certificados reales en `certs/`.
4. **Ejecuta la Batería de Pruebas**:
   ```bash
   python simular_suite_completa_benchmarks.py
   python simular_tormenta_solar_resiliencia.py
   ```
5. **Haz Commit de tus Cambios**:
   ```bash
   git commit -m "feat(core): añadir conmutación de sensores ópticos en tiempo real"
   ```
6. **Envía un Pull Request (PR)** hacia la rama `main`.

---

## 🔬 Estándares de Arquitectura y Código

- **Modelado Cinemático 3D**: Todas las coordenadas deben validarse mediante conversión ECEF-LLA (algoritmo de Bowring) sobre el elipsoide WGS84.
- **Sub-Agentes LoRA**: Los nuevos adaptadores deben mantener una huella de memoria optimizada (≤ 0.25 MB de VRAM por nodo).
- **Notificaciones y Telemetría**: Cualquier modificación en el flujo de alertas debe mantener compatibilidad con el esquema NDJSON/ISO-8601 para Grafana Loki y ElasticSearch.

---

## 📬 Notificación de Vulnerabilidades

Si descubres un problema de seguridad o fallo crítico de telemetría, por favor abre una **Security Advisory** privada en GitHub o contacta directamente con el equipo de mantenedores.
