# Registro de decisiones

Formato: ID · fecha · decisión · motivo · estado. Las decisiones pendientes del autor van al final.

## Tomadas en la fase 0 (11-nov-2026)

**D-001 · Fuente principal: series históricas mensuales SIPSA_P (Excel del DANE, 2013–2026).**
Motivo: son la historia más larga, oficial y descargable con URL fija (10 archivos). Estado: vigente.

**D-002 · Fuentes de respaldo.**
- Microdatos del catálogo 776 o datos.gov.co `gkqq-k3k5` (2013–2024), para validar la carga.
- Servicio SOAP SIPSA, para datos recientes o semanales.
- Anexos semanales, para la historia semanal reciente.

Estado: vigente. El SOAP se probará en la fase 1.

**D-003 · El MVP es mensual y solo de Corabastos.**
Motivo: la historia semanal está repartida en unos 52 archivos por año con nombres irregulares, o depende de un SOAP sin probar. Estado: vigente. Se revisa tras la fase 1.

**D-004 · Paloquemao entra solo si el Excel trae precios para ese mercado.**
Motivo: por ahora solo se confirmó en abastecimiento. Estado: **resuelta** — sí trae precios desde 2013 (79–104 productos por año); se muestra como línea de comparación.

**D-005 · Madrid (Cundinamarca) no tiene precio propio.**
Decisión del autor (11-nov-2026): Corabastos es la **referencia para Bogotá y la Sabana**, y así se rotula en la página. No se inventa ni se interpola un "precio de Madrid". Estado: vigente.

**D-006 · `data/raw/` no se sube a git.**
Se versiona `data/manifest.json` (URL, fecha, tamaño, SHA-256) para que cualquiera reproduzca la descarga. Motivo: las condiciones de los microdatos del DANE prohíben la reproducción electrónica para múltiples usuarios sin autorización, y además los archivos pesan. Estado: vigente.

**D-007 · Inmutabilidad de los crudos.**
- El script nunca sobrescribe un archivo de `data/raw/`.
- Si el DANE reemplaza un archivo en la misma URL (caso del Excel de 2026), la nueva versión se guarda con el sufijo `__AAAAMMDD`.
- Si un crudo cambia en disco, el script emite una alerta.

Estado: vigente e implementado.

**D-008 · Ingesta con biblioteca estándar más PyYAML.**
No se usa `requests` porque `urllib` alcanza para descargas GET con reintentos. Estado: vigente.

**D-009 · Exógenas del MVP: ONI (NOAA CPC) y festivos (paquete `holidays`, clase `CO`).**
Quedan para después:
- IPC de alimentos (falta el enlace exacto del anexo).
- Precipitación (Open-Meteo o CHIRPS; son consultas parametrizadas, no archivos fijos).

Estado: vigente.

**D-010 · El ACPM / diésel se descarta en el MVP.**
Motivo: no se encontró una serie pública descargable, y su precio es regulado y cambia en escalones. Estado: vigente.

**D-011 · Nombres de archivo normalizados en `data/raw/`.**
Siguen el patrón `sipsa_p_serie_mensual_AAAA.xlsx`. La URL original queda en el manifiesto. Motivo: el DANE nombra los archivos de forma irregular entre años. Estado: vigente.

## Tomadas en la fase 1 (11-nov-2026)

**D-012 · Un lector para todos los formatos.** El DANE cambió el Excel seis veces (hoja por año, por mes o única;
"Fuente" o "Mercado"; tres nombres para el precio; códigos CPC y DIVIPOLA desde 2025). El lector busca el encabezado
por nombre, no por posición, y falla con mensaje si no reconoce las columnas. Estado: vigente.

**D-013 · Catálogo como datos.** Unidades (nota al pie del DANE), renombres y mercados viven en
`config/productos.yaml`. Solo se unen series que no se solapan, son contiguas, del mismo grupo y del mismo
producto; las parejas que no se unen quedan escritas con su motivo. Estado: vigente.

**D-014 · Duplicados y saltos.** Duplicado con el mismo precio: se deja uno. Con precio distinto: se descartan
ambos y se reporta (no se elige al azar). Saltos de ×3 entre meses: se reportan en `calidad.json` y no se
tocan (14 casos en Bogotá, casi todos hierbas como cilantro). Estado: vigente.

**D-015 · Consejo de temporada solo si gana a la línea base.** Perfil estacional por producto con su error
estándar; se aconseja "suele subir/bajar el próximo mes" solo si el cambio típico supera el 3 % y 2 errores
estándar. Validado con origen rodante desde 2018 sin mirar el futuro: acierta 78,2 % (IC 95 % 76,2 %–80,2 %,
1.644 casos, 104 productos) frente a 73,7 % de repetir lo del año anterior. Se muestra porque supera ambas
vallas (línea base y 55 %). Se recalcula en cada ejecución: si deja de ganar, la página lo oculta sola. Estado: vigente.

**D-016 · Pesos corrientes en la fase 1.** "Barato o caro" se mide contra la mediana de los 12 meses anteriores,
lo que absorbe la inflación del último año. La versión deflactada queda para la fase 2. Estado: vigente.

**D-017 · Los derivados no se versionan.** `data/procesado/` se regenera con un comando y contiene datos del DANE
(D-006). La página `mercado.html` se publicará cuando se revise la licencia (S9). Estado: vigente.

## Decisiones del autor resueltas

1. MVP mensual: **sí** (fase 1 construida sobre la serie mensual).
2. Madrid: **Corabastos como referencia de Bogotá y la Sabana** (D-005).

## Decisiones para la fase 2 (11-nov-2026, delegadas por el autor)

**D-018 · Pesos corrientes y versión deflactada.** Los modelos trabajan en logaritmo con pesos corrientes
(lo que se paga). La página mostrará además la variación real, descontando el IPC de alimentos del DANE,
para separar "sube por inflación" de "sube por temporada". Requiere descargar la serie del IPC (se agregará
a `config/fuentes.yaml`). Estado: vigente.

**D-019 · Productos prioritarios.** La fase 2 empieza con los 18 productos de la canasta de referencia:
tienen serie completa desde 2013 y cubren lo que más pesa en el mercado de un hogar. Luego se amplía a todos
los que tengan al menos 10 años de historia. Estado: vigente.

**D-020 · SOAP semanal en espera.** Se sigue con la serie mensual; lo semanal se evalúa después de la fase 2.
Estado: vigente.

## Tomadas en las fases 2 y 3 (11-nov-2026)

**D-018 (revisada) · Versión sin inflación aplazada.** No se pudo descargar el IPC desde este entorno
(el sitio del DANE no está permitido) y no es parte de la ficha del proyecto. Los modelos trabajan con
cambios logarítmicos, que no la necesitan. Queda como mejora futura; enlace del anexo de variaciones del
IPC (septiembre de 2026): https://www.dane.gov.co/files/operaciones/IPC/sep2026/anex-IPC-Variacion-sep2026.xls

**D-021 · Aprendizaje profundo solo si gana.** N-BEATS se implementó con JAX y se entrenó en CPU, con
el mismo protocolo que los demás. Perdió contra el ingenuo en los tres horizontes: no se despliega.

**D-022 · Tres líneas base obligatorias.** Ingenuo, estacional ajustado y el perfil de la fase 1.
Un modelo solo se despliega si mejora a la mejor de ellas.

**D-023 · Regla de despliegue con significancia, fijada antes de la prueba.** La mejora en validación debe
tener IC 90 % > 0 con bootstrap de orígenes completos (los productos de un mismo mes no son independientes).
Resultado: LightGBM a 1 mes; ingenuo calibrado a 2 y 3 meses.

**D-024 · No se cambia la selección mirando la prueba.** En la prueba LightGBM también ganó a 2 y 3 meses.
Se mantiene la selección y se reevalúa cuando haya una ventana de validación nueva (p. ej. con datos de 2027:
validación 2023-11 a 2025-10 y prueba 2025-11 en adelante).

**D-025 · Calibración conformal (CQR).** Los intervalos de cada familia se ensanchan con los errores de
validación. En la prueba la cobertura del 10–90 quedó entre 82,6 % y 83,3 % (meta 80 %).

**D-026 · Pronóstico solo para los 18 productos evaluados.** El modelo global podría pronosticar los 160,
pero solo se validó en los 18 de la canasta. La página lo dice en los demás.

**D-027 · Grupos de movimiento no se muestran.** La silueta fue 0,08 (estructura débil). Se muestran solo
los vecinos con ρ ≥ 0,5, que sí son claros.

**D-028 · Publicación.** La página se publica como página web privada del autor (enlace de claude.ai), con
cita al DANE y sin los datos crudos (D-006, S9). El repositorio de GitHub espera la decisión del autor.

**D-029 · Revisión independiente (11-nov-2026).** Un agente que no escribió el código revisó fugas,
protocolo, cifras y página. No encontró fugas y reprodujo la selección. Se corrigió:
- (crítico) el pronóstico leía el panel de la corrida anterior; ahora se escribe antes y el proceso falla si
  el mes del pronóstico y el del tablero no coinciden;
- los cambios de nivel tenían 75–83 % de falsas alarmas; ahora se calibran contra simulaciones sin cambio;
- las cifras por producto mezclaban horizontes; se recalcularon desde la única corrida de prueba;
- el pronóstico ahora exige también los mismos datos crudos de la validación;
- tres errores menores del JavaScript y dos textos.
Quedan documentadas como limitaciones la fragilidad del bootstrap (D-024), el filtro de productos con toda
la muestra y las versiones de las exógenas (`docs/modelos.md`).

## Adenda del 17-nov-2026 (escrita ANTES de volver a correr el experimento)

**D-030 · Corrección de errores de método y repetición única de la prueba.**

La auditoría independiente (`docs/auditoria_independiente.md`, 17-nov-2026) encontró errores en el
**método** con que se eligió y se evaluó el modelo. No se encontró ninguno en los datos. Se corrigen en este
orden (versión 1.1.0, commit «Paso 2»), siguiendo lo que ya decían `docs/modelos.md` y `config/modelos.yaml`:

- **(a) Lista de productos de entrenamiento con datos del futuro.** Los modelos globales (LightGBM y
  N-BEATS) elegían sus productos contando los meses de **toda** la muestra (≥ 120). Eso usaba
  información posterior a cada origen.
  - Ahora la lista se elige en cada reentrenamiento con los precios hasta el origen.
  - Contados así, ningún producto llega a 120 meses antes de 2022-12, porque el panel empieza en
    2013-01. Por decisión del autor, el mínimo es `min(120, meses transcurridos)`: en los orígenes
    tempranos se exige la historia completa.
  - Productos de entrenamiento resultantes: 114 en 2021-11, 103 en 2022-11, 138 en 2023-11 y 160 al final.
- **(b) Calibración conformal (CQR).** Se tomaba el elemento k+1 de los errores ordenados. Ahora se toma
  el k = ⌈(n+1)·0,8⌉ que indica Romano et al. (2019).
- **(c) Bootstrap y regla de despliegue:**
  1. `docs/modelos.md` prometía `bootstrap_bloque` en la configuración, pero no estaba. El código usaba
     en silencio bloques de 1 mes, como si los orígenes consecutivos fueran independientes.
  2. Se fija `bootstrap_bloque: 3`. Razón: el documento exige «bloques de al menos h meses», el
     horizonte máximo es 3 y hay una sola clave, así que 3 es el único valor fijo que cumple la regla en
     todos los horizontes.
  3. Los bloques ahora son **circulares**. Los bloques móviles anteriores sorteaban menos los
     orígenes de los extremos y desplazaban el IC.
  4. b = h y b = 6 se reportan solo como **sensibilidad descriptiva**: no cambian la decisión.
  5. La regla se aplica **tal como está escrita**: se toma el modelo de menor pérdida de cuantiles en
     validación y se despliega solo si su IC 90 % frente a la mejor línea base es mayor que 0. Si no,
     se despliega la mejor línea base. Ya no se recurre al segundo mejor.
- Nuevas pruebas (`tests/test_auditoria.py`) para los cuatro errores que las pruebas no detectaban:
  SARIMAX con el futuro, CQR con datos de la prueba, bootstrap de casos sueltos y validación con
  objetivos dentro de la prueba.

**Por qué se repite la prueba.** La ventana de prueba (2023-11 a 2026-09) ya se usó una vez, el
11-nov-2026. Se usa **una segunda y última vez** (`prueba --forzar`, que queda anotado como `forzada: true`)
**por la corrección de errores de método, no por sus resultados**.
- Ninguna de las tres correcciones se eligió mirando la prueba. (a) y (b) arreglan errores de
  implementación. En (c), el tamaño de bloque sale del texto de `docs/modelos.md`.
- Transparencia: la auditoría sí calculó IC con varios bloques en validación y en prueba antes de esta
  adenda. Por eso el bloque no se eligió entre esas cifras, sino con la regla escrita.
- No se agrega la corrección por comparaciones múltiples (Bonferroni) que sugirió la auditoría. No
  estaba en la regla escrita y añadirla ahora sería cambiar la regla después de ver resultados. Queda
  como limitación declarada.

**Compromiso previo.**
- Se despliega lo que diga la regla, sin excepciones.
- Si LightGBM a 1 mes ya no cumple, se despliega el ingenuo calibrado y se dice así.
- Si algún modelo pasa a cumplir a 2 o 3 meses, se despliega por la misma regla.
- El registro anterior queda intacto en `models/registro_antes/` y en la etiqueta git `estado-auditado`.
- `docs/modelos.md` publicará ambas versiones lado a lado.

**Lo que no cambia en esta corrida:**
- El hallazgo 7 (saltos ×3 a través de huecos, solo de reporte) queda pendiente.
- Las dudas sobre versiones de los datos y el horizonte efectivo siguen como limitaciones.

## Decisiones que necesita el autor

1. **Publicar el repositorio en GitHub** (NowMarket) cuando lo considere listo. Aún no existe `.github/workflows/`: falta crear la integración continua.
