# Estado (17-nov-2026)

- **Versión 1.1.0**, rama `main`, sin push. Repositorio de GitHub: NowMarket; paquete `mercado_al_dia`.
- **Auditoría independiente cerrada.** Corregidos: lista de entrenamiento con datos hasta el origen, orden de
  CQR y bootstrap de bloques circulares (D-030). Línea base anterior en `models/registro_antes/` y etiqueta
  `estado-auditado`.
- **Desplegado:** ingenuo calibrado en 1, 2 y 3 meses. LightGBM no supera la valla en validación.
- **Pruebas:** 71 pasan y 1 es un fallo esperado (con `.[dev,dl]`); CI en Windows y Linux, Python 3.11 y 3.12.
- **Ventana de prueba 2023-11 a 2026-09: gastada** (usada dos veces). Una decisión nueva necesita datos posteriores.
- **Pendiente:** hallazgo 7 es solo de reporte (ya está en `calidad.json`); falta la prueba esperada como fallo,
  que mide `saltos_extremos`. Sin corregir: comparaciones múltiples en la regla, versiones de los datos y de
  la NOAA, y el horizonte real a 1 mes (2 a 3 semanas).
- **No hecho:** push, repositorio en GitHub, actualizar la página publicada en claude.ai (D-028).
- **Dato sospechoso:** pastas de Paloquemao, 2024-02, 394 $/kg; se conserva sin cambios.
