# Ficha: LightGBM, pronóstico a 1 mes (desplegado)

**Uso.** Pronóstico del precio mayorista en Corabastos el mes siguiente, para los 18 productos de la
canasta de referencia, con mediana e intervalo del 80 %.

**Modelo.** LightGBM global (todos los productos con al menos 120 meses), directo para h = 1, tres
regresiones de cuantiles (10, 50 y 90) sobre y = log p(t+1) − log p(t). 300 árboles, tasa 0,05,
15 hojas, mínimo 40 casos por hoja, submuestreo 0,8. Semilla fija (20261111), modo determinista.

**Variables (todas conocidas en el origen t).** Cambios de 1, 3, 6 y 12 meses; distancia a la media de 12
meses; volatilidad de 12 meses; cambio del año anterior y de hace dos años en los mismos meses; mes
objetivo y mes de origen; grupo de alimento; ONI en t−2 y su cambio de 3 meses; variación anual de las
toneladas que entran a Corabastos en t−1.

**Calibración.** CQR con los errores de validación: el intervalo se ensancha 0,0173 en log (≈ 1,7 %).

**Validación sin fuga.** Origen rodante 2021-11 a 2023-10 (selección) y 2023-11 a 2026-09 (prueba única).

| Métrica (prueba, 629 casos) | LightGBM | Ingenuo |
|---|---|---|
| Pérdida de cuantiles (log) | 0,0297 | 0,0312 |
| Error típico de la mediana | 9,2 % | 9,7 % |
| MASE (log) | 0,92 | 0,96 |
| Cobertura 10–90 | 83,3 % | 81,6 % |
| Acierto de dirección | 57,7 % | — |

Mejora sobre el ingenuo: 5,1 % en validación (IC 90 % 1,3–8,7 %) y 4,8 % en prueba (IC 90 % 1,0–8,7 %).

**Sesgos y límites.**
- Ganancia pequeña sobre "el precio se mantiene": el valor está sobre todo en un rango bien calibrado.
- Por producto (prueba a 1 mes), el error típico va de 1,3 % (arroz) a 19,6 % (cebolla cabezona blanca);
  en papa pastusa, papa criolla, mora y zanahoria la cobertura baja a 74–77 %: los choques recientes
  (El Niño 2026) superan lo visto en validación.
- La decisión de desplegarlo en validación es frágil si se respeta la autocorrelación entre meses (con
  bloques de 6 orígenes el IC 90 % incluye 0); en la prueba la mejora se sostiene con cualquier bloque.
- Mayorista no es consumidor. Pesos corrientes.

**Cuándo no usarlo.** Para productos fuera de los 18 evaluados; para más de un mes (ahí se usa el
ingenuo calibrado); ante un choque conocido que aún no está en los datos (paro, cierre de vías).
