# Fase 2: modelos de pronóstico

Fecha: 11-nov-2026. Registro completo en `models/registro/` (`seleccion.json`, `prueba.json` y los
pronósticos de cada origen). Huellas: configuración `0f02a6c4…`, datos `b1bc8ed7…` (SHA-256 de los
crudos del manifiesto). Se generaron con el código en su versión 0.2.0; las versiones posteriores solo
agregan robustez al experimento y no cambian los resultados.

## Pregunta

¿Cuánto costará en Corabastos, en 1, 2 y 3 meses, cada uno de los 18 productos de la canasta
de referencia? La respuesta es un rango: lo más probable (mediana) y el intervalo donde el precio
cae 8 de cada 10 veces (cuantiles 10 y 90).

## Protocolo (fijado en `config/modelos.yaml` antes de ver la prueba)

| Paso | Qué se hizo |
|---|---|
| Datos | Log-precio mensual de Corabastos, 2013-01 a 2026-10 (166 meses, 222 productos). Los modelos globales entrenan con los 160 productos que tienen al menos 120 meses; se evalúan los 18 de la canasta |
| Exógenas | ONI centrado en t−2 (la temporada que termina en t−1 se publica en t); en SARIMAX, t−5 para que el valor de t+3 ya se conozca. Toneladas que entran a Corabastos en t−1 |
| Origen rodante | Para cada mes t se pronostica t+1, t+2, t+3 usando solo precios hasta t. Reentrenamiento cada 12 orígenes, solo con objetivos observados hasta el origen. Prueba automatizada: `test_ningun_modelo_mira_el_futuro` |
| Validación | Orígenes 2021-11 a 2023-10; se conservan solo objetivos dentro de la validación |
| Calibración | CQR (Romano et al., 2019): con los errores de validación se ensancha el intervalo de cada familia y horizonte para cubrir el 80 % |
| Selección | Por horizonte, la familia de menor pérdida de cuantiles en validación, **solo si** mejora a la mejor línea base con IC 90 % > 0 (bootstrap de 2.000 remuestreos de orígenes completos). Si no, se despliega la línea base |
| Prueba | Orígenes 2023-11 a 2026-09. Se corrió **una sola vez**; el código se niega a repetirla (`test_experimento_exige_validacion_y_usa_la_prueba_una_sola_vez`) |
| Comparación justa | Todas las familias se miden sobre los mismos casos (producto, origen, horizonte): 1.169 en validación y 1.833 en prueba |

## Familias

| Familia | Tipo | Descripción |
|---|---|---|
| Ingenuo | línea base | El precio no cambia; el rango sale de los cambios históricos a h meses del mismo producto |
| Estacional ajustado | línea base | Repite el cambio del mismo par de meses del año anterior |
| Perfil estacional | línea base | El perfil de temporada de la fase 1 (media móvil 2×12) llevado a pronóstico |
| SARIMAX | estadístico | SARIMA(1,1,1)(0,1,1)₁₂ por producto sobre el log-precio, con ONI rezagado |
| LightGBM | aprendizaje automático | Global y directo por horizonte; regresión de cuantiles (10/50/90); 14 variables conocidas en el origen |
| N-BEATS | aprendizaje profundo | Genérico, 4 bloques doblemente residuales, ventana de 24 meses, pérdida de cuantiles; JAX en CPU |

## Resultados de validación (después de la calibración)

| h | Gana | Mejora sobre la mejor línea base (ingenuo) | IC 90 % | ¿Se despliega? |
|---|---|---|---|---|
| 1 | LightGBM | 5,1 % | [1,3 %; 8,7 %] | **Sí** |
| 2 | LightGBM | 4,6 % | [−1,4 %; 10,5 %] | No: se usa el ingenuo calibrado |
| 3 | LightGBM | 1,7 % | [−5,2 %; 8,7 %] | No: se usa el ingenuo calibrado |

SARIMAX no mejoró significativamente al ingenuo en ningún horizonte. N-BEATS fue peor que el ingenuo
en los tres (−17 %, −15 % y −15 %), con intervalos muy estrechos antes de calibrar (cobertura de 42 %
a 52 %): **no se despliega** (principio de honestidad del modelo y D-021).

## Resultados de la prueba (una sola vez; pérdida de cuantiles en log, menor es mejor)

| h | LightGBM | SARIMAX | Perfil | Ingenuo | N-BEATS | Est. ajustado |
|---|---|---|---|---|---|---|
| 1 | **0,0297** | 0,0303 | 0,0308 | 0,0312 | 0,0356 | 0,0444 |
| 2 | **0,0476** | 0,0482 | 0,0490 | 0,0501 | 0,0547 | 0,0717 |
| 3 | **0,0572** | 0,0597 | 0,0614 | 0,0630 | 0,0661 | 0,0890 |

Modelos desplegados, en la prueba:

| h | Modelo | Error típico de la mediana (% del precio) | MASE (log) | Cobertura 10–90 (meta 80 %) | Ancho medio del rango |
|---|---|---|---|---|---|
| 1 | LightGBM | 9,2 % | 0,92 | 83,3 % | 37,7 % |
| 2 | Ingenuo calibrado | 16,0 % | 1,54 | 83,0 % | 75,5 % |
| 3 | Ingenuo calibrado | 20,2 % | 1,91 | 82,6 % | 102,5 % |

**Lectura honesta.** En la prueba, LightGBM también le ganó al ingenuo en 2 y 3 meses (5,1 % y 9,1 %,
con IC 90 % [0,4 %; 9,5 %] y [4,3 %; 13,7 %]). La regla fijada antes exigía que eso se viera en
validación, y no se vio. No se cambia la decisión mirando la prueba: se revisará con la próxima
ventana de validación (D-024). La calibración funcionó: la cobertura quedó entre 82,6 % y 83,3 %.

**Por producto (LightGBM a 1 mes, prueba; `models/registro/prueba_por_producto.csv`).** El error típico
va de 1,3 % (arroz de primera) y 1,5 % (queso campesino) a 13,5–19,6 % (cebolla junca, mora, tomate,
papas, zanahoria y cebolla cabezona). La cobertura baja a 74–77 % en papa pastusa, papa criolla, mora
y zanahoria: los choques de 2025–2026 fueron más grandes que los de la validación.

**Sensibilidad del bootstrap (revisión independiente).** La regla registrada remuestrea orígenes sueltos,
pero los orígenes consecutivos comparten choques (autocorrelación de la diferencia de pérdidas: +0,17 a
1 mes, +0,45 a 2 meses y +0,67 a 3 meses). Con bloques de orígenes consecutivos, el IC 90 % de la mejora de
LightGBM a 1 mes en **validación** pasa de [1,3 %; 8,7 %] a [0,5 %; 9,6 %] (bloques de 3) y a [−1,1 %; 9,7 %]
(bloques de 6): la decisión de desplegarlo era frágil y además no corrige por comparar tres candidatos.
En la **prueba**, la mejora a 1 mes se sostiene con cualquier bloque: [1,0 %; 8,7 %], [1,1 %; 9,0 %] y
[2,4 %; 9,9 %]. La próxima validación usará bloques de al menos h meses (`bootstrap_bloque` en
`config/modelos.yaml`; D-024).

**Variables más útiles en LightGBM** (ganancia media): distancia a la media de 12 meses (18 %),
cambio del año anterior en los mismos meses (12 %), grupo de alimento (10 %), cambio de hace dos
años (9 %), último cambio mensual (8 %), cambio anual (7 %), ONI (7 %). El abastecimiento aporta 4,5 %.

## Minería (`mineria.py`)

- **Movimiento conjunto.** Correlación de los cambios mensuales sin la temporada, 160 productos.
  El agrupamiento jerárquico tiene estructura débil (silueta 0,08 con 15 grupos), así que la página
  **no** muestra los grupos; muestra solo los vecinos con ρ ≥ 0,5 (p. ej. papa pastusa y papa superior,
  ρ = 0,99; plátano hartón verde y llanero, 0,94). Tablas: `vecinos.csv`, `grupos_movimiento.csv`.
- **Cambios de nivel.** PELT sobre el log-precio sin temporada, en los 18 productos evaluados. La revisión
  independiente mostró que, sin control, PELT marca "cambios" en 75–83 % de series simuladas que no
  los tienen (los precios son muy persistentes). Ahora cada producto tiene un umbral: el percentil 95 del
  cambio que el mismo detector encuentra en 200 series AR(1) simuladas sin cambio real, ajustadas a ese
  producto. La página muestra el cambio solo si es reciente (24 meses), de al menos 15 % y mayor que ese
  umbral. Tabla: `cambios_de_nivel.csv` (con el umbral y si se muestra).
  Con datos hasta 2026-10 ninguno de los 18 pasa el umbral (p. ej., el +68 % de la papa pastusa en
  2026-05 queda por debajo de su umbral de 99,6 %: esa serie salta así a menudo sin cambio de nivel).
- **Sustitutos.** Los define el autor (`config/sustitutos.yaml`); la página los usa para ajustar la
  canasta a un presupuesto.

## Limitaciones conocidas (revisión independiente)

- **Productos de entrenamiento.** Los modelos globales entrenan con productos que tienen al menos 120
  meses contados en toda la muestra, no hasta cada origen. No filtra ningún objetivo, pero deja fuera
  2 productos que existían en 2021-11 (leche en polvo, pollo entero). Se corrige en la próxima validación;
  cambiarlo ahora invalidaría la reproducción exacta del registro.
- **Versiones de las exógenas.** El ONI y el abastecimiento se usan en su versión actual, no en la que
  estaba publicada en cada origen. Las revisiones del ONI suelen ser de centésimas; el efecto debería ser
  pequeño, pero no se midió.
- **Trayectoria mixta.** A 1 mes pronostica LightGBM y a 2–3 meses el ingenuo; un alza a 1 mes puede
  "volver" al precio actual a 2 meses. La página lo explica junto al pronóstico.

## Cómo repetirlo

```
python -m mercado_al_dia                                   # fase 1, minería y pronóstico
python -m mercado_al_dia.modelos.experimento validacion    # elige y calibra (unos 40 s)
python -m mercado_al_dia.modelos.experimento prueba        # una sola vez
```
N-BEATS requiere `pip install -e .[dl]` (JAX). Sin JAX el experimento lo omite y lo dice.
