# Fase 2: modelos de pronóstico

**Versión vigente: 1.1.0 (17-nov-2026).** La corrida del 11-nov-2026 (versión 0.2.0) tenía errores de método
que encontró la auditoría independiente (`docs/auditoria_independiente.md`). Se corrigieron (D-030) y el
experimento se repitió **una sola vez**, con la prueba marcada `forzada: true`. El motivo fue la corrección,
no los resultados.

Este documento publica las dos versiones lado a lado:
- Registro vigente: `models/registro/`, con huellas de configuración `f7da5490…` y datos `b1bc8ed7…`.
- Registro anterior, intacto: `models/registro_antes/`, con su `modelos_publicado.md` y la etiqueta git
  `estado-auditado`. Huellas de configuración `0f02a6c4…` y datos `b1bc8ed7…`.
- Los datos crudos son los mismos en ambas versiones.

## Resultado en una línea

**Con la regla corregida, LightGBM ya no se despliega a 1 mes.** Su mejora en validación (+4,2 %) tiene IC 90 %
[−0,7 %; +8,6 %] con bloques de 3 orígenes: no supera la valla. En los tres horizontes se despliega el **ingenuo
calibrado**. En la prueba LightGBM fue mejor, pero la regla se fijó antes y se decide en validación (D-024,
D-030), así que no se rescata.

## Pregunta

¿Cuánto costará en Corabastos, en 1, 2 y 3 meses, cada uno de los 18 productos de la canasta
de referencia? La respuesta es un rango: lo más probable (mediana) y el intervalo donde el precio
cae 8 de cada 10 veces (cuantiles 10 y 90).

## Protocolo: qué cambió

| Paso | 0.2.0 (11-nov) | 1.1.0 (17-nov, vigente) |
|---|---|---|
| Datos | Log-precio mensual de Corabastos, 2013-01 a 2026-10 (166 meses, 222 productos); se evalúan los 18 de la canasta | Igual |
| Productos de entrenamiento de LightGBM y N-BEATS | Los 160 con ≥ 120 meses **en toda la muestra**, en todos los orígenes (usaba el futuro) | En cada reentrenamiento, los que tienen ≥ min(120, meses transcurridos) meses **hasta el origen**: 114 (2021-11), 103 (2022-11), 138 (2023-11), 150 (2024-11), 158 (2025-11) |
| Exógenas | ONI centrado en t−2 (t−5 en SARIMAX); abastecimiento de t−1 | Igual. La auditoría confirmó que va un mes por detrás de lo publicado |
| Origen rodante | Pronóstico de t+1, t+2 y t+3 con precios hasta t; reentrenamiento cada 12 orígenes | Igual |
| Validación | Orígenes 2021-11 a 2023-10, objetivos dentro de la validación | Igual |
| Calibración (CQR) | Elemento k+1 de los errores ordenados (de más) | Elemento k = ⌈(n+1)·0,8⌉ (Romano et al., 2019) |
| Bootstrap de la regla | Orígenes sueltos (bloque 1 por defecto; `bootstrap_bloque` no estaba en la configuración) | Bloques **circulares** de 3 orígenes (`bootstrap_bloque: 3`, el único valor fijo ≥ h en h = 1, 2 y 3); b = h y b = 6 solo como sensibilidad descriptiva |
| Regla | Entre los modelos significativos, el de menor pérdida (podía rescatar al segundo) | **Tal como está escrita**: el de menor pérdida se despliega solo si su IC 90 % > 0; si no, la mejor línea base |
| Prueba | Orígenes 2023-11 a 2026-09; primera y única corrida | Misma ventana; segunda y última corrida, `forzada: true`, por corrección de método |
| Comparación justa | 1.169 casos en validación y 1.833 en prueba, comunes a todas las familias | Igual: 1.169 y 1.833 |

## Familias

| Familia | Tipo | Descripción |
|---|---|---|
| Ingenuo | línea base | El precio no cambia; el rango sale de los cambios históricos a h meses del mismo producto |
| Estacional ajustado | línea base | Repite el cambio del mismo par de meses del año anterior |
| Perfil estacional | línea base | El perfil de temporada de la fase 1 (media móvil 2×12) llevado a pronóstico |
| SARIMAX | estadístico | SARIMA(1,1,1)(0,1,1)₁₂ por producto sobre el log-precio, con ONI rezagado |
| LightGBM | aprendizaje automático | Global y directo por horizonte; regresión de cuantiles (10/50/90); 14 variables conocidas en el origen |
| N-BEATS | aprendizaje profundo | Genérico, 4 bloques doblemente residuales, ventana de 24 meses, pérdida de cuantiles; JAX en CPU |

## Validación y regla de despliegue (después de calibrar)

Mejora de la pérdida de cuantiles del mejor modelo (LightGBM en los tres horizontes y en las dos versiones)
sobre la mejor línea base (el ingenuo):

| h | 0.2.0: mejora | 0.2.0: IC 90 % (orígenes sueltos) | 0.2.0: ¿se desplegó? | 1.1.0: mejora | 1.1.0: IC 90 % (bloques circulares de 3) | 1.1.0: ¿se despliega? |
|---|---|---|---|---|---|---|
| 1 | 5,1 % | [1,3 %; 8,7 %] | **Sí**, LightGBM | 4,2 % | [−0,7 %; 8,6 %] | **No**: ingenuo calibrado |
| 2 | 4,6 % | [−1,4 %; 10,5 %] | No | 4,6 % | [−4,7 %; 13,1 %] | No: ingenuo calibrado |
| 3 | 1,7 % | [−5,2 %; 8,7 %] | No | 1,3 % | [−8,5 %; 10,2 %] | No: ingenuo calibrado |

**Sensibilidad descriptiva** (1.1.0; no cambia la decisión):

| h | bloque = h | bloque = 6 |
|---|---|---|
| 1 | [+0,2 %; +7,9 %] | [−1,1 %; +9,1 %] |
| 2 | [−4,0 %; +12,7 %] | [−5,4 %; +13,9 %] |
| 3 | [−8,5 %; +10,2 %] | [−8,9 %; +9,9 %] |

Con bloque 1 (orígenes sueltos, como en la 0.2.0) LightGBM a 1 mes seguiría pasando por poco. Eso muestra
cuánto dependía la decisión anterior de tratar como independientes meses que no lo son: la autocorrelación de
la diferencia de pérdidas es +0,17, +0,45 y +0,67 a 1, 2 y 3 meses.

**Otras familias:**
- SARIMAX no mejora al ingenuo con significancia en ningún horizonte.
- N-BEATS es peor que el ingenuo en los tres: −15,6 %, −12,7 % y −7,5 % (antes −17 %, −15 % y −15 %).
- Antes de calibrar, los intervalos de N-BEATS son muy estrechos: cubren 40–48 % (antes 42–52 %).
- N-BEATS no se despliega (D-021).

**Limitación declarada.** La regla compara 3 candidatos por horizonte sin corregir por comparaciones múltiples.
La auditoría lo señaló, pero no está en la regla escrita y no se agregó después de ver resultados (D-030).

## Prueba (pérdida de cuantiles en log; menor es mejor)

| h | versión | LightGBM | SARIMAX | Perfil | Ingenuo | N-BEATS | Est. ajustado |
|---|---|---|---|---|---|---|---|
| 1 | 0.2.0 | 0,0297 | 0,0303 | 0,0308 | 0,0312 | 0,0356 | 0,0444 |
| 1 | 1.1.0 | 0,0298 | 0,0302 | 0,0308 | **0,0312** | 0,0357 | 0,0444 |
| 2 | 0.2.0 | 0,0476 | 0,0482 | 0,0490 | 0,0501 | 0,0547 | 0,0717 |
| 2 | 1.1.0 | 0,0473 | 0,0480 | 0,0489 | **0,0501** | 0,0562 | 0,0717 |
| 3 | 0.2.0 | 0,0572 | 0,0597 | 0,0614 | 0,0630 | 0,0661 | 0,0890 |
| 3 | 1.1.0 | 0,0569 | 0,0593 | 0,0614 | **0,0630** | 0,0662 | 0,0890 |

En negrita, lo desplegado en la 1.1.0.

**Modelos desplegados, en la prueba:**

| h | 0.2.0: modelo | 0.2.0: error típico | 0.2.0: cobertura | 0.2.0: ancho | 1.1.0: modelo | 1.1.0: error típico | 1.1.0: cobertura | 1.1.0: ancho |
|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 9,2 % | 83,3 % | 37,7 % | **Ingenuo calibrado** | 9,7 % | 80,6 % | 38,4 % |
| 2 | Ingenuo calibrado | 16,0 % | 83,0 % | 75,5 % | Ingenuo calibrado | 16,0 % | 82,8 % | 74,9 % |
| 3 | Ingenuo calibrado | 20,2 % | 82,6 % | 102,5 % | Ingenuo calibrado | 20,2 % | 82,3 % | 101,9 % |

Definiciones y metas:
- Error típico: media de |real − mediana| / real.
- Cobertura: rango 10–90, con meta de 80 %.
- Ancho: ancho medio del rango.
- MASE (log) del ingenuo: 0,96, 1,54 y 1,91.

La corrección de CQR estrecha un poco los rangos y acerca la cobertura a la meta.

**Lectura honesta.** En la prueba, LightGBM vuelve a ganarle al ingenuo en los tres horizontes. Mejora en
4,7 %, 5,7 % y 9,7 %, con IC 90 % de bloques de 3: [0,4 %; 8,5 %], [−0,6 %; 11,4 %] y [2,8 %; 16,0 %].
- La regla, fijada antes de esta corrida, exige que la mejora se vea en validación.
- Con 23 orígenes de validación y la dependencia entre meses, no se vio con la seguridad exigida.
- No se cambia la decisión mirando la prueba (D-024, D-030).
- LightGBM se reevaluará con una ventana de validación nueva, por ejemplo con datos de 2027: validación de
  2023-11 a 2025-10 y prueba desde 2025-11.

Esta prueba ya se usó dos veces y **no debe volver a usarse** para decidir.

**Por producto (ingenuo calibrado, prueba; `models/registro/prueba_por_producto.csv`):**

| h | error típico | cobertura por producto | productos con menor cobertura |
|---|---|---|---|
| 1 | 1,4 % a 20,0 % | 68,6 % a 97,1 % | papa criolla 68,6 %; cebolla cabezona, naranja, huevo y zanahoria 74,3 % |
| 2 | 2,1 % a 36,3 % | 61,8 % a 100 % | papa criolla 61,8 %, zanahoria 64,7 % |
| 3 | 2,4 % a 47,3 % | 57,6 % a 100 % | zanahoria 57,6 %, huevo rojo A y papa criolla 69,7 % |

Los choques de 2025–2026 fueron mayores que los de la validación.

**Variables más útiles en LightGBM** (ganancia media, 1.1.0; el modelo no se despliega):

| Variable | Ganancia |
|---|---|
| Distancia a la media de 12 meses | 18 % |
| Cambio del año anterior en los mismos meses | 12 % |
| Grupo de alimento | 9 % |
| Cambio de hace dos años | 9 % |
| Último cambio mensual | 8 % |
| Cambio anual | 7 % |
| ONI | 7 % |
| Abastecimiento | 4,7 % |

## Minería (`mineria.py`)

- **Movimiento conjunto.** Correlación de los cambios mensuales sin la temporada, 160 productos.
  - El agrupamiento jerárquico tiene estructura débil (silueta 0,08 con 15 grupos), así que la página
    **no** muestra los grupos.
  - Muestra solo los vecinos con ρ ≥ 0,5. Por ejemplo, papa pastusa y papa superior, ρ = 0,99; plátano
    hartón verde y llanero, 0,94.
  - Tablas: `vecinos.csv`, `grupos_movimiento.csv`.
- **Cambios de nivel.** PELT sobre el log-precio sin temporada, en los 18 productos evaluados.
  - La revisión independiente mostró que, sin control, PELT marca «cambios» en 75–83 % de series simuladas
    que no los tienen (los precios son muy persistentes).
  - Ahora cada producto tiene un umbral: el percentil 95 del cambio que el mismo detector encuentra en 200
    series AR(1) simuladas sin cambio real, ajustadas a ese producto.
  - La página muestra el cambio solo si es reciente (24 meses), de al menos 15 % y mayor que ese umbral.
    Tabla: `cambios_de_nivel.csv`, con el umbral y si se muestra.
  - Con datos hasta 2026-10 ninguno de los 18 pasa el umbral. Por ejemplo, el +68 % de la papa pastusa en
    2026-05 queda por debajo de su umbral de 99,6 %: esa serie salta así a menudo sin cambio de nivel.
- **Sustitutos.** Los define el autor (`config/sustitutos.yaml`); la página los usa para ajustar la
  canasta a un presupuesto.

## Limitaciones conocidas

- **Comparaciones múltiples.** La regla no corrige por comparar 3 candidatos por horizonte (ver arriba).
- **Versiones de las exógenas y de los precios.** El ONI, el abastecimiento y los Excel del SIPSA se usan en
  su versión actual, no en la que estaba publicada en cada origen. Los Excel anuales se reeditan en enero del
  año siguiente. El efecto debería ser pequeño, pero no se puede medir sin copias antiguas.
- **Horizonte efectivo.** El precio de t se publica entre el 6 y el 17 de t+1. El pronóstico «a 1 mes» se
  emite con t+1 ya empezado, así que su horizonte real es de unas 2–3 semanas.
- **Prueba gastada.** La ventana 2023-11 a 2026-09 se usó dos veces (11 y 17 de noviembre). La próxima
  decisión requiere una ventana nueva.
- Corregido en la 1.1.0: la lista de productos contados en toda la muestra, el orden estadístico de CQR y el
  bootstrap sin bloques. Ya no son limitaciones.

## Cómo repetirlo

```
python -m mercado_al_dia                                   # fase 1, minería y pronóstico
python -m mercado_al_dia.modelos.experimento validacion    # elige y calibra
python -m mercado_al_dia.modelos.experimento prueba        # se niega si ya existe models/registro/prueba.json
```
N-BEATS requiere `pip install -e .[dl]` (JAX). Sin JAX el experimento lo omite y lo dice.
