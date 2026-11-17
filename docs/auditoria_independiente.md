# Auditoría independiente — NowMarket (entonces «Mercado al Día») v1.0

Fecha: 17-nov-2026. No se modificaron resultados, modelos, código, configuración ni datos del proyecto.
Lo único que se agregó es este informe y la carpeta `docs/auditoria_independiente/` (scripts y una prueba
que pytest no recoge por defecto). No se hizo commit (la carpeta no es un repositorio git).

**Alcance de la lectura.** Se leyeron solo `README.md`, `docs/modelos.md`, `docs/decisiones.md`,
`docs/supuestos.md`, `config/modelos.yaml`, `models/registro/` y el código de `src/mercado_al_dia/modelos/`
y `src/mercado_al_dia/sipsa/`. Como datos (no como documentación) se usaron los crudos de `data/raw/`,
`data/manifest.json`, `config/productos.yaml` (catálogo de renombres y unidades, lo aplica `sipsa/panel.py`),
`data/procesado/validacion_estacional.csv` y la ficha `models/model_cards/consejo_estacional.md` (única
definición escrita del consejo de temporada, necesaria para la tarea 3). `tests/` se **ejecutó** para las
mutaciones, pero no se leyó. `analisis.py` no se leyó: el perfil estacional se comprobó desde fuera.

**Entorno.** Python 3.11.9, pandas 3.0.0, numpy 2.4.1, LightGBM 4.7.0, statsmodels 0.15.0. Faltan `ruptures` y
`jax`. Todo se ejecutó sobre una **copia** del proyecto en una carpeta temporal.

## Resumen

| # | Gravedad | Hallazgo | Estado |
|---|---|---|---|
| 1 | **Media** | La decisión de desplegar LightGBM a 1 mes descansa en un IC que trata como independientes los orígenes consecutivos y no corrige por comparar 3 candidatos. Con corrección de Bonferroni la cota inferior es −0,02 %. `bootstrap_bloque` no está en la configuración aunque `docs/modelos.md` dice que sí | Demostrado |
| 2 | **Media** | Bootstrap por bloques (`metricas.bootstrap_mejora`, `bloque>1`) no circular: los orígenes de los extremos pesan menos y el IC se desplaza. El «se sostiene con cualquier bloque» de la prueba depende de ese sesgo | Demostrado |
| 3 | **Media** | Fuga por selección: la lista de productos con los que entrenan los modelos globales se elige con meses posteriores al origen. En 2021-11 la regla configurada da 0 productos, no 160. La prueba que lo demuestra falla. El efecto en los resultados es pequeño y no cambia la selección | Demostrado |
| 4 | **Media** | Las pruebas no detectan 4 de 8 errores realistas: fuga en SARIMAX, CQR con datos de la prueba, bootstrap de casos y objetivos de la validación dentro de la prueba | Demostrado |
| 5 | Baja | CQR toma un orden estadístico de más: el k+1, no el ⌈(n+1)·0,8⌉. Esto ensancha los rangos de forma sistemática | Demostrado |
| 6 | Baja | Documentación: S14 dice 67–72 %, pero el registro da 57,6–64,7 % en zanahoria y papa criolla a 2–3 meses. `precios_bogota.csv` y `.github/workflows/` no existen | Demostrado |
| 7 | Baja | Datos: 4 saltos ×3 a través de huecos no se reportan; pasta en Paloquemao a 394 $/kg (salto ×24) queda en el panel | Demostrado |
| 8 | Duda | Versiones de los datos (SIPSA reeditado en enero del año siguiente, ONI revisado), uso único de la prueba sin registro inmutable y horizonte «1 mes» que en realidad es el mes en curso | No demostrable |

**Lo que sí se sostiene:**
- Integridad de datos: 30 de 30 precios coinciden y los 67.036 registros de Bogotá cuadran.
- No hay fuga temporal de precios ni de exógenas con el calendario real de publicación.
- Las cifras publicadas se reproducen exactamente: 9,2 %, 83,3/83,0/82,6 %, pérdida de cuantiles y −4,8 %.
- El consejo de temporada da 78,2 % frente a 73,7 % (reproducido dentro de 0,2 pp).
- La prueba no se usó para elegir.
- El código actual (1.0.0) reproduce el registro de la 0.2.0 con diferencias de 1,8·10⁻¹⁵.

---

## Hallazgos por gravedad

### 1. (Media) La regla de despliegue a 1 mes es más frágil de lo que dice el registro

**Qué se registró.** `seleccion.json`: LightGBM a 1 mes mejora 5,13 % al ingenuo, con IC 90 % [1,26 %; 8,66 %].
El código remuestrea orígenes completos con `bloque = cfg.get("bootstrap_bloque", 1)`
(`evaluacion.py:92`). `config/modelos.yaml` **no tiene** `bootstrap_bloque`; `docs/modelos.md:82` afirma que sí.
Por eso los orígenes se remuestrean como si fueran independientes.

**Evidencia** (`t4_bootstrap.py`, validación calibrada, 20.000 remuestreos, implementación propia):

| h | orígenes | mejora | ρ₁ de la diferencia de pérdidas | iid | bloques circulares b=3 | b=6 | DM (Newey-West) |
|---|---|---|---|---|---|---|---|
| 1 | 23 | +5,13 % | +0,17 | [1,2; 8,7] | [0,7; 9,4] | [0,05; 9,8] | t = −1,98 |
| 2 | 22 | +4,62 % | +0,45 | [−1,5; 10,4] | [−3,5; 12,1] | [−4,1; 12,7] | t = −0,94 |
| 3 | 21 | +1,71 % | +0,67 | [−5,1; 8,3] | [−7,9; 10,6] | [−8,2; 10,5] | t = −0,28 |

- La autocorrelación que reporta `docs/modelos.md` (+0,17 / +0,45 / +0,67) se reproduce exactamente.
- **Comparaciones múltiples.** Se prueban 3 candidatos por horizonte (LightGBM, SARIMAX, N-BEATS) sin
  corregir. Con Bonferroni para 3 candidatos y orígenes iid, la cota inferior de LightGBM a 1 mes es
  **−0,02 %**: la mejora ya no es significativa.
- Con 23 orígenes (2 años) cualquier IC es inestable. El estadístico Diebold-Mariano con errores HAC
  queda en el límite (|t| ≈ 2).

**Consecuencia.** El despliegue a 1 mes resultó acertado en la prueba (mejora de 4,84 %; IC iid [0,8; 8,6],
circular b=6 [0,4; 9,1]). Pero la regla registrada no lo demostraba con robustez, y la regla anunciada para la
próxima validación («bloques de al menos h») sigue usando b=1 en h=1.

### 2. (Media) El bootstrap por bloques del repositorio está sesgado en los extremos

`metricas.bootstrap_mejora` con `bloque>1` sortea los inicios en `[0, n−b]` sin dar la vuelta. Un origen en la
posición i aparece en min(i+1, b, n−i) bloques posibles, así que los primeros y últimos b−1 orígenes pesan
menos. En la ventana de prueba eso mueve el IC (`t4_bootstrap.py`, columna «móvil» frente a «circ»):

| Prueba | móvil b=6 (como el repo) | circular b=6 |
|---|---|---|
| LightGBM h=1 | [2,3 %; 9,9 %] | [0,4 %; 9,1 %] |
| LightGBM h=2 | [1,5 %; 12,7 %] | [−2,2 %; 11,6 %] |
| LightGBM h=3 | [5,2 %; 17,8 %] | [0,9 %; 16,4 %] |

La frase de `docs/modelos.md` «en la prueba la mejora a 1 mes se sostiene con cualquier bloque … [2,4 %; 9,9 %]»
se reproduce solo con la versión sesgada. Con bloques circulares el resultado sigue siendo positivo, pero el
intervalo es bastante más ancho. Esto importa porque D-024 deja esta función como regla de la próxima validación.

### 3. (Media) Fuga por selección de los productos de entrenamiento

`datos.cargar` (`datos.py:94-95`) calcula `entrenamiento` con los meses de **toda** la muestra (≥ 120). La lista
se usa en todos los orígenes. Esta es la «prueba que falla» que pide la tarea 2
(`docs/auditoria_independiente/test_auditoria_publicacion.py::test_lista_de_entrenamiento_solo_con_lo_publicado`):

```
origen 2021-11: 160 productos con la muestra completa frente a 0 con lo publicado hasta el origen
origen 2023-11: 160 … frente a 138; sobran 22 (p. ej. 'ahuyamin sakata', 'azucar morena', 'banano bocadillo')
origen 2025-11: 160 … frente a 158; sobran 2 ('camaron titi precocido seco', 'cebolla cabezona roja')
```

- **La regla tal como está escrita es imposible de aplicar sin mirar el futuro.** Antes de 2022-12 ningún
  producto puede tener 120 meses (la serie empieza en 2013-01). Es decir, durante casi toda la validación
  la lista existe solo porque se conoce el futuro.
- La lista también excluye productos que luego desaparecieron (sesgo de supervivencia). `docs/modelos.md`
  lo describe como «deja fuera 2 productos», lo que subestima el problema.
- **Efecto medido** (`t2_efecto_lista.py`, regla factible: ≥ 72 % de los meses disponibles hasta t, que equivale
  a 120/166, con lista recalculada en cada reentrenamiento):

  | h | pérdida registrada | mejora | pérdida con lista factible | mejora | IC90 iid |
  |---|---|---|---|---|---|
  | 1 | 0,03071 | +5,13 % | 0,03085 | +4,70 % | [+0,49 %; +8,49 %] |
  | 2 | 0,04878 | +4,62 % | 0,04859 | +4,99 % | [−1,26 %; +11,12 %] |
  | 3 | 0,06098 | +1,71 % | 0,06013 | +3,07 % | [−3,33 %; +9,64 %] |

  La selección no cambia, aunque a 1 mes la cota inferior baja de 1,26 % a 0,49 %.
- Con la lista fija, **todo lo demás está libre de fuga**: las 15 combinaciones de familia × origen de
  `test_pronostico_identico_con_solo_lo_publicado` pasan. Ver la tarea 2.

### 4. (Media) Las pruebas automáticas no detectan 4 de 8 errores realistas

Cada mutante se aplicó a la copia, se corrió `pytest tests` y se restauró el archivo (`t5_mutacion.py`).
La línea base en este entorno es 48 que pasan, 2 que fallan por falta de `ruptures` y 1 omitida por falta de
`jax`. Un mutante cuenta como detectado si falla alguna de las 48.

| Id | Error introducido | Archivo | ¿Lo detecta `tests/`? | Prueba que lo detecta | ¿Lo detecta la prueba de auditoría? |
|---|---|---|---|---|---|
| M1 | Fuga de un mes: LightGBM entrena con objetivos hasta t+1 | `familias.py` | Sí | `test_ningun_modelo_mira_el_futuro[LightGBMGlobal]` | Sí |
| M2 | `dev12` con media de 12 meses centrada (usa 6 meses futuros) | `familias.py` | Sí | ídem | Sí |
| M3 | ONI sin rezago de publicación (temporada que termina en t+1) | `familias.py` | Sí | `test_caracteristicas_usan_exogenas_con_rezago` | Sí |
| M4 | Abastecimiento del mes t+1 | `familias.py` | Sí | las dos anteriores | Sí |
| **M5** | **SARIMAX estimado con toda la serie** | `familias.py` | **No** | — (SARIMAX no está en la prueba de fuga) | Sí |
| **M6** | **CQR recalculado con los datos de la prueba** | `experimento.py` | **No** | — | no aplica |
| **M7** | **Bootstrap de casos (producto × origen), no de orígenes** | `metricas.py` | **No** | — | no aplica |
| **M8** | **La validación conserva objetivos dentro de la ventana de prueba** | `experimento.py` | **No** | — | no aplica |

- **M6** haría que la cobertura de la prueba diera ~80 % por construcción y escondería la sobre o
  subcobertura real.
- **M8** contamina la elección con meses de la prueba.
- **M5** es una fuga directa en un modelo que se compara en la regla de despliegue.
- **M7** no cambia la decisión en estos datos (IC de casos a 1 mes [0,6 %; 9,4 %]), pero ninguna prueba
  protege esa propiedad, que D-023 declara esencial.

La prueba de auditoría (lista fija, datos truncados al momento de publicación) detecta M1–M5.

### 5. (Baja) CQR toma un orden estadístico de más

`evaluacion.cqr` usa `np.quantile(e, ceil((n+1)·0,8)/n, method="higher")`, que devuelve el elemento ordenado
número ⌈(n+1)·0,8⌉ **+ 1**. Romano et al. (2019) usan el número ⌈(n+1)·0,8⌉. Se comprobó así:
- La fórmula del código, aplicada a `pronosticos_validacion.csv`, reproduce los 18 ajustes de `seleccion.json`
  con diferencias de 1,8·10⁻¹⁵. Esto también prueba que la calibración usó **solo la validación**.
- La fórmula estándar da ajustes entre 0,00001 y 0,004 log menores. Por ejemplo, ingenuo h=1: 0,00314 frente
  a 0,00526; SARIMAX h=1: −0,00045 frente a 0,00097.

El efecto es pequeño y conservador: la cobertura calibrada en validación queda en 80,6 % en todas las familias,
y contribuye un poco al 82,6–83,3 % de la prueba.

### 6. (Baja) Documentación que no coincide con el registro o con el repositorio

- **S14** (`supuestos.md`): «Falla en papas y zanahoria (67–72 %)». No coincide con ningún horizonte desplegado
  de `prueba_por_producto.csv`:
  - LightGBM h=1: 74,3–77,1 %, como dice `modelos.md`.
  - Ingenuo h=2: papa criolla 61,8 %, zanahoria 64,7 %.
  - Ingenuo h=3: zanahoria 57,6 %, papa criolla 69,7 %, huevo rojo A 72,7 %.

  A 2–3 meses la cobertura por producto es peor de lo que se declara.
- `docs/modelos.md:82` cita `bootstrap_bloque` en `config/modelos.yaml`, pero no está.
- `README.md` lista `data/procesado/precios_bogota.csv` (y la tarea lo pedía), pero **no existe en el
  proyecto**. Hubo que regenerarlo en una copia. La huella de los crudos coincide con el registro
  (`b1bc8ed7…`) y los 13 SHA-256 del manifiesto coinciden.
- `README.md` y D-028 mencionan `.github/workflows/pruebas.yml`, que no existe.
- La huella de la configuración (`0f02a6c4…`) coincide con la actual.

### 7. (Baja) Datos: casos extremos que pasan sin aviso

- Los 14 saltos ×3 de `calidad.json` se reproducen. Hay **4 más a través de huecos** que el código no revisa
  (`panel.py:327` solo mira meses consecutivos):

  | Mercado | Producto | Desde | Hasta | Precio antes | Precio después |
  |---|---|---|---|---|---|
  | Corabastos | coliflor | 2017-07 | 2017-10 | 2.400 | 650 |
  | Corabastos | feijoa | 2023-07 | 2025-10 | 4.635 | 15.000 |
  | Corabastos | mandarina común | 2013-12 | 2014-02 | 903 | 3.145 |
  | Paloquemao | pastas alimenticias | 2022-05 | 2024-02 | 8.222 | 394 |

- Pasta en Paloquemao: 394 $/kg en 2024-02 y 9.600 en 2024-03 (×24). Casi seguro es un error de la fuente o
  de unidad. Se reporta, pero sigue en la línea de comparación.
- «Jugo instantáneo (sobre)» queda en $/kg. La nota del DANE solo habla de «jugo de frutas» en $/litro.
  La unidad real es **dudosa**. No está en la canasta.

### 8. Dudas (no demostrables con lo disponible)

- **Versiones de los datos.** Los Excel de 2018–2023 tienen «Fecha de actualización» del 6 al 17 de enero del año
  siguiente, y el de 2013–2017 del 30-may-2018. Son reediciones anuales. Si el DANE corrigió meses dentro del año,
  el origen rodante usa cifras que no existían en esa forma en el origen. No hay copias antiguas para medirlo.
  Lo mismo vale para el ONI, que se recalcula con ERSST y cambios de climatología (ya declarado en `modelos.md`).
- **Uso único de la prueba.** A favor:
  - `seleccion.json` (20:31:04) precede a `prueba.json` (20:31:44), con la misma huella y `forzada: false`.
  - La selección no cambió aunque LightGBM ganó a 2 y 3 meses en la prueba.

  Sin embargo, el candado es la mera existencia de `prueba.json`: borrar el archivo permite repetirla sin
  rastro, y no hay historial git. Tampoco se puede demostrar que `config/modelos.yaml` se fijó antes de ver
  la prueba.
- **«1 mes» es el mes en curso.** El precio de t sale entre el día 6 y el 17 de t+1. El pronóstico «a 1 mes»
  se emite ya empezado t+1 y apunta al promedio de t+1. No es una fuga, porque no se usa nada de t+1, pero el
  horizonte efectivo es de unas 2–3 semanas, no un mes.

---

## Tarea 1 — Integridad de los datos

**Archivo.** `data/procesado/precios_bogota.csv` no existe (hallazgo 6). Se regeneró en una copia con
`python -m mercado_al_dia <copia>`. Se escribe antes de fallar en minería por falta de `ruptures`, y queda con
67.036 filas.

**Muestra.** 30 filas con `numpy.random.default_rng(20261117)`, verificadas con un lector propio (`openpyxl`, sin
importar el proyecto) en la celda que indica su origen (archivo, hoja, fila). Se compararon fecha, producto
original, mercado y precio. Resultado: **30/30 coinciden, 0 diferencias**. La tabla completa está en
`docs/auditoria_independiente/t1_muestra_salida.md`. Cinco celdas se releyeron además directamente por número
de fila.

**Conciliación completa** (`t1_global.py`):
- Filas crudas de Bogotá: 67.036, sin fechas ilegibles ni precios no numéricos.
- Claves (mes, mercado, producto): 67.036, sin faltantes ni sobrantes, y **0 precios distintos**.
- Total de filas crudas leídas: 767.549, igual que S8.

| Revisión | Resultado |
|---|---|
| Duplicados | 0 idénticos y 0 en conflicto en Bogotá, igual que `calidad.json` |
| Renombres | Los 3 cumplen D-013 en Corabastos: sin solape, contiguos y del mismo grupo. Ciruela negra chilena 2013-01..2015-06 → ciruela negra importada 2015-08 → ciruela importada desde 2015-09; galletas saladas 3 tacos hasta 2015-07 → galletas saladas desde 2015-08. Conteos 18/1/93, iguales a `calidad.json` |
| Unidades | Encabezados de los 10 Excel: un solo campo de precio por hoja. La nota al pie ($/unidad para huevos y bocadillo; $/litro para aceite y vinagre) se aplica a 9 productos. No hay cambio de nivel en el cambio de archivo: la mediana del cambio en enero es 0,051, igual a la de los otros meses (0,051). Huevo, aceite y bocadillo son continuos entre 2017, 2018 y 2019 |
| Saltos extremos | 14 de 14 reproducidos, más 4 a través de huecos (hallazgo 7) |

**Diferencias contadas: 0** en la muestra y 0 en la conciliación completa.

## Tarea 2 — Fecha de publicación

**Calendario real, con la evidencia de los propios crudos:**

| Fuente | Evidencia | Se publica | El código usa en el origen t |
|---|---|---|---|
| Precio SIPSA del mes t | «Fecha de actualización» 6–17 de enero (diciembre); el Excel 2026 bajado el 11-nov trae octubre | día 6–17 de t+1 | precios ≤ t |
| ONI | `oni.ascii.txt` del 11-nov-2026 trae ASO-2026 (centrada en sep, termina en oct) | temporada que termina en m, a comienzos de m+1 | centrado en t−2 (LightGBM); t−5 para t+3 (SARIMAX) |
| Abastecimiento | «Fecha de actualización: 6 de noviembre de 2026» con octubre-2026 | mes m, ~día 6 de m+1 | mes t−1 |

En el momento del pronóstico τ(t) (≥ día 6 de t+1) se conocen precios ≤ t, el ONI centrado ≤ t−1 y el
abastecimiento ≤ t. El código usa **menos** de lo disponible: el ONI y el abastecimiento van un mes por detrás
de lo publicado. Es conservador y correcto.

**Prueba.** `test_pronostico_identico_con_solo_lo_publicado` borra todo lo publicado después de τ(t), reentrena
y compara con tolerancia 1e-9. Familias: ingenuo, estacional ajustado, perfil estacional, SARIMAX y LightGBM.
Orígenes: 2021-11, 2023-11 y 2025-11. **Pasan las 15.** La misma prueba detecta los mutantes M1–M5.

**Fuga demostrada:** solo la selección de productos de entrenamiento (hallazgo 3). Su prueba falla en los 3 orígenes.

```
set MAD_RAIZ=<copia con data/procesado/precios_bogota.csv>
python -m pytest -q -p no:cacheprovider docs/auditoria_independiente/test_auditoria_publicacion.py
→ 3 failed (lista de entrenamiento), 15 passed (pronóstico con lo publicado)
```

## Tarea 3 — Reimplementación independiente

Los scripts `t3_metricas.py` y `t3_consejo.py` solo usan numpy y pandas y no importan el proyecto.

| Cifra publicada | Reimplementación | Fuente |
|---|---|---|
| Pérdida de cuantiles en la prueba, 18 combinaciones de modelo × h (p. ej. LightGBM 0,0297 / 0,0476 / 0,0572) | Idénticas (máx. dif. 8·10⁻¹⁷) | `pronosticos_prueba.csv` frente a `prueba.json` |
| Error típico a 1 mes: 9,2 % (media de \|real − mediana\| / real) | 9,243 % | ídem |
| Cobertura 10–90 de lo desplegado: 83,3 / 83,0 / 82,6 % | 83,31 / 82,98 / 82,63 % | ídem |
| −4,8 % frente al ingenuo a 1 mes (5,1 % y 9,1 % a 2 y 3) | 4,84 / 5,10 / 9,13 % | ídem |
| Casos comunes: 1.169 en validación y 1.833 en prueba | 407+390+372 y 629+611+593 | ídem |
| Pérdida calibrada en validación: LightGBM h=1 0,03071; ingenuo 0,03237 | 0,03071; 0,03237 | `pronosticos_validacion.csv` + CQR registrado |
| Consejo «suele subir/bajar»: 78,2 %, 1.644 casos, 104 productos | **78,16 %, 1.644 casos, 104 productos** | precios regenerados + especificación de la ficha |
| Línea base del año anterior: 73,7 % | 73,5 % (73,4 % en todos los 1.644 casos) | ídem |

**Consejo de temporada.** Se reimplementó así:
- media móvil 2×12 sobre el log y residuo medio por mes del calendario;
- consejo si el cambio es ≥ 3 % y mayor que 2 errores estándar (ddof=1, combinados sin correlación);
- al menos 5 años por mes;
- orígenes de 2018-01 a 2026-09.

Coincide producto a producto salvo 3 casos en el límite: arroz de primera 12 frente a 14, huevo rojo AA 9 frente
a 8 y mandarina arrayana 71 frente a 70. La causa está en detalles que la ficha no fija, como el umbral exacto o
el trato de los empates. Las diferencias de ±0,2 pp quedan como **duda menor de especificación**, no como error.

**Observaciones sobre el consejo:**
- La ventana 2018–2026 se superpone con la prueba de los modelos y los umbrales se fijaron con los mismos datos.
  No es una estimación sobre datos reservados.
- Aun así, la ventaja se sostiene:
  - Solo en 2023-11..2026-09: 77,0 % frente a 69,9 %.
  - IC 95 % por bootstrap de meses de origen: acierto [75,9 %; 80,5 %], ventaja [+3,2; +7,3] pp.

## Tarea 4 — Regla de despliegue

- **La prueba no se usó para elegir:**
  - `seleccion.json` es anterior a `prueba.json` y tiene la misma huella.
  - Los 18 ajustes CQR se reproducen solo con la validación.
  - `seleccionar` usa únicamente la tabla de validación calibrada.
  - La selección no cambió pese a que LightGBM ganó a 2 y 3 meses en la prueba.
  - Queda la duda del candado (hallazgo 8).
- **El IC del 90 % no respeta la dependencia entre meses consecutivos:**
  - El registro usa orígenes iid (`bootstrap_bloque` ausente; hallazgo 1).
  - Con bloques circulares y corrección por 3 candidatos, la mejora a 1 mes en validación deja de ser
    claramente significativa.
  - La implementación de bloques disponible está sesgada en los extremos (hallazgo 2).

## Tarea 5 — Mutación

Ver la tabla del hallazgo 4. **No detectados por `tests/`: M5, M6, M7, M8.**

## Cómo reproducir

Desde la raíz, en Git Bash. `C` es una copia del proyecto con el panel regenerado:

```
cp -r config data docs models src tests pyproject.toml README.md "$C/"
PYTHONPATH="$C/src" python -m mercado_al_dia "$C"               # escribe precios_bogota.csv (falla después si falta ruptures)
A=docs/auditoria_independiente
python -I $A/t1_leer_crudo.py "$C/data/raw" crudo.pkl            # lector independiente: 767.549 filas
python -I $A/t1_muestra.py  "$C/data/procesado/precios_bogota.csv" crudo.pkl "$C/data/raw"
python -I $A/t1_global.py   "$C/data/procesado/precios_bogota.csv" crudo.pkl "$C/data/procesado/calidad.json"
python -I $A/t1_unidades.py "$C/data/procesado/precios_bogota.csv"
python -I $A/t3_metricas.py models/registro val_cal.pkl
python -I $A/t3_consejo.py  "$C/data/procesado/precios_bogota.csv" data/procesado/validacion_estacional.csv
python -I $A/t4_bootstrap.py val_cal.pkl ; python -I $A/t4_bootstrap.py models/registro/pronosticos_prueba.csv
PYTHONPATH="$C/src" python $A/t2_efecto_lista.py "$C" models/registro
MAD_RAIZ="$C" PYTHONPATH="$C/src" python -m pytest -q -p no:cacheprovider $A/test_auditoria_publicacion.py
python $A/t5_mutacion.py "$C" mutacion.json                      # modifica y restaura archivos de la COPIA
```
