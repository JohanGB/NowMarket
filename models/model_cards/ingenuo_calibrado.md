# Ficha: ingenuo calibrado, pronóstico a 1, 2 y 3 meses (desplegado desde v1.1)

**Qué es.** Lo más probable es que el precio siga igual. El rango sale de los cambios históricos a 1, 2 o 3
meses del mismo producto (últimos 10 años, solo datos hasta el origen). Luego se ensancha con CQR para cubrir
el 80 %: 0,0031 en log a 1 mes, 0,0196 a 2 meses y 0,0180 a 3 meses.

**Por qué se despliega.** En validación (2021-11 a 2023-10) el modelo de menor pérdida en los tres horizontes
fue LightGBM. Su mejora sobre el ingenuo no tuvo IC 90 % > 0 con bootstrap de bloques circulares de 3 meses:

| h | Mejora | IC 90 % |
|---|---|---|
| 1 | +4,2 % | [−0,7 %; +8,6 %] |
| 2 | +4,6 % | [−4,7 %; +13,1 %] |
| 3 | +1,3 % | [−8,5 %; +10,2 %] |

La regla de `config/modelos.yaml` despliega entonces la mejor línea base, que es el ingenuo (D-030).
En la v1.0, LightGBM se desplegaba a 1 mes porque el bootstrap trataba como independientes los meses
consecutivos; ver `docs/auditoria_independiente.md`.

| Prueba (2023-11 a 2026-09) | 1 mes | 2 meses | 3 meses |
|---|---|---|---|
| Error típico de la mediana | 9,7 % | 16,0 % | 20,2 % |
| MASE (log) | 0,96 | 1,54 | 1,91 |
| Cobertura 10–90 (meta 80 %) | 80,6 % | 82,8 % | 82,3 % |
| Ancho medio del rango | 38,4 % | 74,9 % | 101,9 % |

**Límites.**
- **No anticipa dirección.** Las alertas para tenderos solo aparecen si todo el rango queda de un lado del
  precio actual.
- **Los rangos son anchos.** A 3 meses el precio puede duplicarse o caer a la mitad en productos volátiles.
- **Cobertura baja en algunos productos.** Papa criolla: 68,6 % a 1 mes y 61,8 % a 2 meses. Zanahoria:
  57,6 % a 3 meses. Los choques de 2025–2026 superan lo visto en validación.
- **LightGBM fue mejor en la prueba en los tres horizontes.** Se reevalúa con una ventana de validación nueva
  (D-024); la prueba actual ya se usó dos veces.
