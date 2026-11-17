# Ficha: LightGBM (NO desplegado desde v1.1, 17-nov-2026)

**Estado.** Se desplegó a 1 mes en la v1.0 (11-nov-2026). Con la regla corregida (D-030) no supera la valla
en validación y **no se usa**. Se conserva la ficha como registro.

**Modelo.** LightGBM global, directo por horizonte, con tres regresiones de cuantiles (10, 50 y 90) sobre
y = log p(t+h) − log p(t).
- Hiperparámetros: 300 árboles, tasa 0,05, 15 hojas, mínimo 40 casos por hoja, submuestreo 0,8.
- Semilla fija (20261111) y modo determinista.
- Productos de entrenamiento elegidos en cada origen solo con datos hasta ese origen: ≥ min(120, meses
  transcurridos) meses con precio. Son 114 en 2021-11 y 158 en 2025-11. En la v1.0 se contaban sobre toda
  la muestra, lo que usaba el futuro.

**Variables (todas conocidas en el origen t):**
- cambios de 1, 3, 6 y 12 meses;
- distancia a la media de 12 meses y volatilidad de 12 meses;
- cambio del año anterior y de hace dos años en los mismos meses;
- mes objetivo y mes de origen;
- grupo de alimento;
- ONI en t−2 y su cambio de 3 meses;
- variación anual de las toneladas que entran a Corabastos en t−1.

**Validación (bootstrap de bloques circulares de 3 orígenes; regla de `config/modelos.yaml`):**

| h | Mejora sobre el ingenuo | IC 90 % | ¿Se despliega? |
|---|---|---|---|
| 1 | +4,2 % | [−0,7 %; +8,6 %] | No |
| 2 | +4,6 % | [−4,7 %; +13,1 %] | No |
| 3 | +1,3 % | [−8,5 %; +10,2 %] | No |

**Prueba** (2023-11 a 2026-09; segunda y última vez, por corrección de método; no se usa para decidir):

| | 1 mes | 2 meses | 3 meses |
|---|---|---|---|
| Pérdida de cuantiles (log) | 0,0298 | 0,0473 | 0,0569 |
| Error típico de la mediana | 9,2 % | 15,6 % | 18,9 % |
| Cobertura 10–90 | 83,5 % | 80,5 % | 85,2 % |
| Mejora sobre el ingenuo | 4,7 % | 5,7 % | 9,7 % |
| IC 90 % de la mejora (bloques de 3) | [0,4 %; 8,5 %] | [−0,6 %; 11,4 %] | [2,8 %; 16,0 %] |

**Por qué no se rescata.** La regla se fijó antes y decide en validación (D-024, D-030). Con solo 23 orígenes de
validación y meses dependientes entre sí, la mejora no se vio con la seguridad exigida. Se reevaluará con una
ventana de validación nueva, por ejemplo con datos de 2027.
