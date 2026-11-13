# Fase 0: viabilidad de datos

**Proyecto:** Mercado al Día
**Fecha de la revisión:** 11 de noviembre de 2026
**Alcance:** comprobar qué datos públicos y gratuitos existen para pronosticar precios mayoristas de alimentos en Bogotá (Corabastos), Paloquemao y Madrid (Cundinamarca). Esta fase no incluye modelos.

---

## 0. Cómo leer este documento

Cada dato lleva una etiqueta que dice qué tan comprobado está:

| Etiqueta | Significado |
|---|---|
| **[ARCHIVO]** | Confirmado abriendo y leyendo el archivo de datos. En esta fase **ningún** dato llegó a este nivel, porque el entorno de trabajo no pudo descargar los archivos (ver sección 7). |
| **[PÁGINA]** | Confirmado en una página o boletín oficial que se leyó en esta sesión. Si es una URL, aparece publicada como enlace en la página oficial citada. |
| **[DOC]** | Tomado de un documento metodológico oficial (ficha, plan general, guía del servicio web). Describe cómo *debería* ser el dato; falta comprobarlo contra el archivo. |
| **[SIN CONFIRMAR]** | Inferencia razonable o enlace que no se pudo verificar. No debe usarse como hecho hasta revisarlo. |

Que un enlace aparezca publicado en una página oficial **no prueba que el archivo abra**. Cuando además se comprobó que abre, se indica como "abre: sí".

---

## 1. Resumen ejecutivo

1. **Sí hay datos para Corabastos.** El SIPSA publica precios mayoristas con el nombre de mercado exacto **"Bogotá, D.C., Corabastos"** [PÁGINA]. Hay series históricas en Excel, una por año, desde 2013 hasta 2026 [PÁGINA].
2. **La historia larga que se descarga fácil es mensual, no semanal.** Las "Series históricas precios mayoristas" (10 archivos Excel, 2013–2026) y los microdatos del DANE (catálogo 776, 2013–2024) tienen un registro por mes, mercado y producto. Esto se deduce del número de filas, unas 54.000 a 57.000 por año ([PÁGINA] microdatos; ver 2.3). La historia semanal existe, pero repartida en **un anexo Excel por semana** (unos 52 archivos al año) o detrás del servicio web SOAP. Por eso es más costosa de reunir.
3. **Paloquemao:** aparece como mercado del SIPSA con el nombre **"Bogotá, D.C., Paloquemao"**, junto con **"Bogotá, D.C., Plaza Las Flores"** y **"Bogotá, D.C., Plaza Samper Mendoza"**. Por ahora solo se confirmó en el cuadro de **abastecimiento** (toneladas) [PÁGINA]. En los cuadros de **precios** de los boletines leídos, Bogotá solo aparece como Corabastos. Que Paloquemao tenga serie de precios queda **[SIN CONFIRMAR]** hasta abrir el Excel histórico.
4. **Madrid (Cundinamarca): no hay mercado SIPSA.** En ninguna lista leída aparece un mercado mayorista en Cundinamarca. El departamento solo figura como **origen** de productos (Mosquera, Funza, Zipaquirá, Chía, Sabana de Bogotá, etc.) [PÁGINA]. La alternativa honesta es usar Corabastos como referencia regional, rotulada como tal, y no presentar ningún precio "de Madrid".
5. **Veredicto: VIABLE CON CONDICIONES** (sección 9). El MVP debe arrancar **mensual** con Corabastos. Lo semanal y Paloquemao dependen de comprobaciones de la fase 1.

---

## 2. Fuentes del componente de precios mayoristas (SIPSA_P)

### 2.1 Páginas oficiales de entrada

| Recurso | URL | Estado |
|---|---|---|
| Página principal SIPSA (DANE) | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa | [PÁGINA] |
| Boletín diario (con histórico por mes 2012–2026) | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/componente-precios-mayoristas | [PÁGINA] |
| Boletín semanal | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/mayoristas-boletin-semanal-1 | [PÁGINA] |
| Boletín semanal, histórico 2025 (página por año) | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/mayoristas-boletin-semanal-1/boletin-mayorista-semanal-2025 | URL salida de búsqueda; contenido [SIN CONFIRMAR] |
| Boletín mensual y **series históricas** | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/mayoristas-boletin-mensual-1 | [PÁGINA] |
| Servicio web SOAP | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/servicio-web-para-consulta-de-la-base-de-datos-de-sipsa | [PÁGINA] |
| Ficha metodológica SIPSA_P (v3, 28-jun-2022) | https://bibliotecadoctecnica.dane.gov.co/static/documentos/DIMPE/SIPSA_P/SIPSA_P_Ficha%20metodol%c3%b3gica.pdf | [PÁGINA], abre: sí |
| Plan general SIPSA_P (DAN-SIPSA_P-PGR-001 v1, 28-jun-2022) | https://bibliotecadoctecnica.dane.gov.co/static/documentos/DIMPE/SIPSA_P/SIPSA_P_Plan%20general.pdf | [PÁGINA], abre: sí |
| "Acerca de SIPSA" (boletín mensual) | https://www.dane.gov.co/files/operaciones/SIPSA/Acerca-de-SIPSA-mensual.pdf | [PÁGINA], abre: sí |
| Microdatos SIPSA_P 2013–2024 (catálogo 776) | https://microdatos.dane.gov.co/index.php/catalog/776 | [PÁGINA], abre: sí |
| Tablero Pentaho (solo consulta) | https://apps.dane.gov.co/pentaho/api/repos/%3Apublic%3ASIPSA%3ASIPSAV17.wcdf/generatedContent | enlace publicado [PÁGINA]; no abierto |
| Geovisor precios mayoristas (solo consulta) | https://geoportal.dane.gov.co/geovisores/territorio/precios-mayoristas-sipsa/ | enlace publicado [PÁGINA]; no abierto |

### 2.2 Tabla de fuentes de precios

| # | Fuente | URL exacta (o patrón) | Formato | Granularidad | Historia | Actualización | Estado |
|---|---|---|---|---|---|---|---|
| P1 | **Series históricas precios mayoristas** (un archivo por año) | Ver lista completa en 2.3 | XLSX | **Mensual** por mercado y producto [SIN CONFIRMAR: deducido del catálogo 776] | 2013 a 2026 | El de 2026 se reemplaza cada mes (el boletín mensual sale el día hábil siguiente al IPC) [DOC] | URLs [PÁGINA]; estructura [SIN CONFIRMAR] |
| P2 | Anexo del **boletín semanal** (uno por semana, de sábado a viernes) | Último: https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-31oct06nov-2026.xlsx | XLSX | Semanal; mínimo, máximo y medio por mercado y producto [PÁGINA, según el boletín PDF] | Boletines semanales desde 22-jun-2012 [DOC] | Viernes, 5 p. m. [DOC] | URL [PÁGINA], abre: sí (WebFetch recibió binario); contenido no legible desde aquí |
| P3 | Anexo del **boletín mensual** | Último: https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSAMensual-sep2026.xlsx | XLSX | Mensual, por ciudad (8 a 10 ciudades principales) [PÁGINA] | Desde jul-2012 [DOC] | Mensual | URL [PÁGINA] |
| P4 | Anexo del **boletín diario** e "Informes por ciudades" | Ej.: https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSADiario-23oct2026.xlsx y https://www.dane.gov.co/files/operaciones/SIPSA/bol-SIPSADiario-regionales-23oct2026.zip | XLSX / ZIP | Diaria (perecederos). Los regionales usan la **unidad de empaque**, no $/kg [DOC] | Desde 12-jun-2012 [DOC] | Días hábiles, mediodía | URLs [PÁGINA] |
| P5 | **Microdatos anonimizados** SIPSA_P | https://microdatos.dane.gov.co/index.php/catalog/776 (descarga en https://microdatos.dane.gov.co/index.php/catalog/776/get-microdata) | Según catálogo: archivos "SIPSA_P-Mensual-AAAA"; formato [SIN CONFIRMAR] | Mensual por mercado y producto | 2013 a 2024 | Anual | Catálogo [PÁGINA]; página de descarga no leída (posible registro) [SIN CONFIRMAR] |
| P6 | **Servicio web SOAP** | WSDL: http://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService?WSDL | SOAP 1.2 / XML | Diaria, semanal y mensual según operación (2.4) | [SIN CONFIRMAR] | Diarios y semanales a las 2 p. m.; mensuales el día 8; abastecimiento el día 10 [PÁGINA] | WSDL publicado [PÁGINA]; no probado |
| P7 | **datos.gov.co**: "Sistema de Información de Precios y Abastecimiento del Sector Agropecuario Componente de Precios Mayoristas – SIPSA - P - 2013 -2024", id Socrata **`gkqq-k3k5`** | https://www.datos.gov.co/dataset/Sistema-de-Informaci-n-de-Precios-y-Abastecimiento/gkqq-k3k5 | Socrata (CSV/JSON por API) [SIN CONFIRMAR] | [SIN CONFIRMAR]; por el título, probablemente igual a P5 | 2013–2024 (según el título) | [SIN CONFIRMAR] | Página existe [PÁGINA]; columnas, filas y licencia [SIN CONFIRMAR]. La API de metadatos no fue accesible. |

**Historia semanal (P2), patrón de nombres** [PÁGINA, histórico 2025]: la página de 2025 enlaza **52 anexos XLSX**, uno por semana. Los nombres **no siguen un patrón regular**:
- https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-28dic-3ene-2025.xlsx (cubre del 28-dic-2024 al 3-ene-2025)
- https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-4ene-10ene-2025.xlsx
- https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-06dic12dic-2025.xlsx
- https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-20dic26dic-2025.xlsx

A veces llevan guion entre fechas y a veces no; unos días van con cero inicial y otros sin él. Por eso las URLs semanales **no se pueden generar con una fórmula**. Hay que leerlas de cada página anual, que se pueden recorrer como HTML con el patrón `.../mayoristas-boletin-semanal-1/boletin-mayorista-semanal-AAAA`. La página de 2014 usa otra ruta (`.../componente-precios-mayoristas-2015/mayoristas-boletin-semanal-1/boletin-mayorista-semanal-2014-1`), así que tampoco ahí hay un patrón fijo. Reunir 2013–2026 serían unos 700 archivos.

Sobre P7: en el mismo portal, otros conjuntos se exportan con el patrón `https://www.datos.gov.co/api/views/<id>/rows.csv?accessType=DOWNLOAD` (visto en resultados de búsqueda, p. ej. con el id `3r8y-jvw8`). Aplicado a `gkqq-k3k5`, el enlace sería https://www.datos.gov.co/api/views/gkqq-k3k5/rows.csv?accessType=DOWNLOAD. Ese enlace es **[SIN CONFIRMAR]**: no se abrió y podría no existir si el conjunto es solo un enlace externo.

### 2.3 Series históricas mensuales: enlaces exactos (P1)

Todos aparecen publicados en la página del boletín mensual [PÁGINA]. **Ojo:** la ruta cambia en 2023. Hasta 2022 los archivos están en `files/investigaciones/agropecuario/sipsa/series-historicas/` y desde 2023 en `files/operaciones/SIPSA/`. El de 2023 se llama `...Dic2023`.

| Año(s) | URL |
|---|---|
| 2013–2017 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas.xlsx |
| 2018 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2018.xlsx |
| 2019 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2019.xlsx |
| 2020 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2020.xlsx |
| 2021 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2021.xlsx |
| 2022 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2022.xlsx |
| 2023 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-Dic2023.xlsx |
| 2024 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-2024.xlsx |
| 2025 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-2025.xlsx |
| 2026 (parcial) | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-2026.xlsx |

**Estructura esperada.** Viene del diccionario de los microdatos equivalentes (catálogo 776), no de los Excel:

| Archivo de microdatos | Filas | Variables |
|---|---|---|
| SIPSA_P-Mensual-2013_2017 | 281.387 | 5 |
| SIPSA_P-Mensual-2018 | 57.121 | 5 |
| SIPSA_P-Mensual-2019 | 56.626 | 5 |
| SIPSA_P-Mensual-2020 | 55.716 | 5 |
| SIPSA_P-Mensual-2021 | 54.528 | 5 |
| SIPSA_P-Mensual-2022 | 53.647 | 5 |
| SIPSA_P-Mensual-2023 | 53.807 | 5 |
| SIPSA_P-Mensual-2024 | 54.042 | **6** |

Variables del archivo 2024 [PÁGINA, diccionario F10]: `Fecha` ("Fecha Programada para la Recolección"), `Grupo`, `Producto` ("Nombre Artículo"), `CODIGO_CPC_AC` ("Código CPC"), `Mercado` ("Nombre de la Fuente") y `Precio_promedio_por_kilogramo_` (etiqueta: "Precio Promedio Diario"). Los archivos anteriores a 2024 tienen 5 variables. La que falta probablemente es `CODIGO_CPC_AC` **[SIN CONFIRMAR]**.

Inferencia sobre la granularidad: unas 55.000 filas al año equivalen a unas 4.600 por mes. Con unos 60 mercados, eso da unos 75 productos por mercado al mes, lo que encaja con un dato **mensual** y no diario. La etiqueta "Precio Promedio Diario" contradice esto, así que la granularidad queda **[SIN CONFIRMAR]** hasta abrir el archivo.

Tamaño aproximado: unas 55.000 filas × 5 o 6 columnas por año sugieren de 1 a 4 MB por archivo XLSX, y unos 20 a 40 MB entre los 10. Es una **estimación [SIN CONFIRMAR]**. Cabe sin problema en 8 GB de RAM.

### 2.4 Servicio web SOAP (P6)

- **WSDL:** http://appweb.dane.gov.co/sipsaWS/SrvSipsaUpraBeanService?WSDL [PÁGINA]. Usa `http`, no `https`.
- **Guía oficial:** https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/DANE-webservice-SIPSA.pdf (marzo de 2020; SOAP 1.2, Java 1.6, ADF, WebLogic 11) [PÁGINA, abre: sí].
- La guía **no incluye** la URL del servicio. La URL sale de la página del DANE.

| Operación | Qué devuelve (según la guía) | Campos [DOC] |
|---|---|---|
| `promediosSipsaCiudad` | Precio promedio de cada producto por ciudad | `ciudad`, `codProducto`, `enviado`, `fechaCaptura`, `fechaCreacion`, `precioPromedio`, `producto`, `regId` |
| `promediosSipsaParcial` | Máximo, mínimo y promedio "parcial" por ubicación y fuente (mercado) | `artiNombre`, `deptNombre`, `enmaFecha`, `fuenNombre`, `futiId`, `grupNombre`, `idArtiSemana`, `maximoKg`, `minimoKg`, `muniId`, `muniNombre`, `promedioKg` |
| `promediosSipsaSemanaMadr` | Máximo, mínimo y promedio **semanal** de un producto por fuente (mercado) | `artiId`, `artiNombre`, `fechaMesIni`, `fuenId`, `fuenNombre`, `futiId`, `maximoKg`, `minimoKg`, `promedioKg` |
| `promediosSipsaMesMadr` | Máximo, mínimo y promedio **mensual** en $/kg por fuente | `artiId`, `artiNombre`, `enviado`, `fechaCreacion`, `fechaMesIni`, `fuenId`, `fuenNombre`, `futiId`, `maximoKg`, `minimoKg`, `promedioKg`, `tmpMayoMesId` |
| `promedioAbasSipsaMesMadr` | Abastecimiento mensual en **toneladas** por producto y fuente. **Solo devuelve registros no consultados antes.** | `artiId`, `artiNombre`, `cantidadTon`, `fechaMesIni`, `fuenId`, `fuenNombre`, `futiId` |
| `consultarInsumosSipsaMesMadr` | Precio mensual de insumos agrícolas por municipio (no aplica al proyecto) | `deptNombre`, `insumoNombre`, `muniNombre`, `promedio`, ... |

Inconsistencias de la guía [PÁGINA]:
- El ejemplo de `promediosSipsaSemanaMadr` usa `fechaIni`, pero la tabla dice `fechaMesIni`.
- `promediosSipsaParcial` lista `futiId` y `futid` por separado.
- En `promediosSipsaCiudad`, `producto` figura como numérico aunque es un nombre.
- La guía dice "kg de recolección" donde se refiere a precio por kg.

Queda sin confirmar si las operaciones aceptan parámetros de fecha o solo devuelven la ventana más reciente. Eso decide si el SOAP sirve para reconstruir **historia semanal**. **[SIN CONFIRMAR]**: se prueba en la fase 1 desde el PC del autor.

---

## 3. Cobertura geográfica: respuesta directa

### 3.1 Mercados de Bogotá

| Nombre exacto en SIPSA | ¿En abastecimiento (toneladas)? | ¿En precios? | Fuente |
|---|---|---|---|
| **Bogotá, D.C., Corabastos** | Sí [PÁGINA] | **Sí [PÁGINA]**: cuadros de precios del boletín diario del 21-oct-2026 y del semanal del 19 al 25-sep-2026 | Boletines citados abajo |
| **Bogotá, D.C., Paloquemao** | Sí [PÁGINA] | **[SIN CONFIRMAR]**: no aparece en los cuadros de precios leídos (lectura parcial: 100.000 de 284.000 caracteres del boletín semanal) | Ídem |
| **Bogotá, D.C., Plaza Las Flores** | Sí [PÁGINA] | [SIN CONFIRMAR] | Ídem |
| **Bogotá, D.C., Plaza Samper Mendoza** | Sí [PÁGINA] | [SIN CONFIRMAR] | Ídem |

Boletines leídos:
- Diario, 21-oct-2026: https://www.dane.gov.co/files/operaciones/SIPSA/bol-SIPSADiario-21oct2026.pdf
- Semanal, 19 al 25-sep-2026 (Núm. 728): https://www.dane.gov.co/files/operaciones/SIPSA/bol-SIPSASemanal-19sep25sep-2026.pdf
- Mensual, sep-2026: https://www.dane.gov.co/files/operaciones/SIPSA/bol-SIPSAMensual-sep2026.pdf. En este nivel aparece "Bogotá" como ciudad, sin nombre de mercado.

Paloquemao y Samper Mendoza son, en la práctica, plazas de flores, hierbas y venta minorista. Por eso es posible que el SIPSA solo mida en ellas **abastecimiento** y no precios, o precios de pocos productos. **[SIN CONFIRMAR]**: lo resuelve en un minuto la primera lectura del Excel histórico (`df["Mercado"].unique()`).

### 3.2 Madrid (Cundinamarca)

- **No hay mercado SIPSA en Madrid ni en ningún municipio de Cundinamarca** en las listas leídas: 32 mercados del cuadro de abastecimiento del boletín diario del 21-oct-2026, y la lista de mercados del boletín semanal del 19 al 25-sep-2026 [PÁGINA].
- Cundinamarca aparece solo como **lugar de origen** de los alimentos: Mosquera, Funza, Zipaquirá, Villapinzón, Fusagasugá, Sibaté, Chía, Fómeque y Sabana de Bogotá, entre otros [PÁGINA].
- **Alternativa honesta:**
  1. Para Madrid, mostrar el precio de **Corabastos** rotulado como "referencia mayorista de Bogotá (Corabastos); no es un precio medido en Madrid".
  2. Opcional: usar los **microdatos de abastecimiento** (que traen departamento y municipio de procedencia [DOC]) para mostrar cuánto de lo que entra a Corabastos *viene de* Madrid o de la Sabana occidente. Que Madrid figure como procedencia es **[SIN CONFIRMAR]**.
  3. No inventar ni interpolar un "precio de Madrid".

### 3.3 Lista de mercados SIPSA leídos (como aparecen)

Del cuadro de abastecimiento del boletín diario del 21-oct-2026 [PÁGINA]: Armenia, Mercar · Barranquilla, Barranquillita · Barranquilla, Granabastos · **Bogotá, D.C., Corabastos** · **Bogotá, D.C., Paloquemao** · **Bogotá, D.C., Plaza Las Flores** · **Bogotá, D.C., Plaza Samper Mendoza** · Bucaramanga, Centroabastos · Cali, Cavasa · Cali, Santa Elena · Cartagena, Bazurto · Cúcuta, Cenabastos · Cúcuta, La Nueva Sexta · Florencia (Caquetá) · Ibagué, Plaza La 21 · Ipiales (Nariño), Centro de acopio · Manizales, Centro Galerías · Medellín, Central Mayorista de Antioquia · Medellín, Plaza Minorista "José María Villa" · Montería, Mercado del Sur · Neiva, Surabastos · Pasto, El Potrerillo · Pereira, La 41-Impala · Pereira, Mercasa · Popayán, Plaza de mercado del barrio Bolívar · Santa Marta (Magdalena) · Sincelejo, Nuevo Mercado · Tibasosa (Boyacá), Coomproriente · Tunja, Complejo de Servicios del Sur · Valledupar, Mercabastos · Valledupar, Mercado Nuevo · Villavicencio, CAV.

El boletín semanal menciona además mercados de precios en municipios intermedios: Chiquinquirá, Duitama, Yopal, Rionegro, Marinilla, La Ceja, Sonsón, Túquerres, La Unión, Pamplona, San Gil, Socorro, Palmira, Tuluá, Cartago, Buenaventura y Arauca, entre otros [PÁGINA, lectura parcial].

Cifras de cobertura que no coinciden entre sí:
- "62 mercados" (Acerca de SIPSA).
- "más de 61 mercados" y 744 fuentes programadas en sep-2026 (boletín mensual).
- 32 mercados en abastecimiento (boletín diario).
- 29 mercados en 21 ciudades (ficha SIPSA_A).

Son universos distintos: precios, fuentes y abastecimiento. Hay que fijar la lista desde los datos y no desde los boletines.

---

## 4. Productos, unidad y tipo de precio

| Aspecto | Hallazgo | Estado |
|---|---|---|
| Número de productos | "Canasta cercana a los 400 productos" | [PÁGINA] Acerca de SIPSA |
| Grupos (8) | Verduras y hortalizas · Frutas · Tubérculos, raíces y plátanos · Granos y cereales · Huevos y lácteos · Carnes · Pescados · Procesados | [DOC] ficha SIPSA_P |
| Unidad | **Pesos colombianos por kilogramo** en la mayoría. Huevos y bocadillo **por unidad**. Aceite, jugos y vinagre **por litro**. Los boletines diarios regionales usan la **unidad de empaque original** | [DOC] plan general; [PÁGINA] boletín mensual (huevo rojo A en Bogotá: $438 por unidad) |
| Tipo de precio | **Mínimo, máximo y medio** por kg (boletín semanal: columnas Mínimo / Máximo / Medio más tendencia) | [PÁGINA] boletín semanal; [DOC] ficha |
| Cálculo del precio medio | **Media aritmética de las "tomas"** del periodo (no es la moda). Una o dos rondas por producto y hasta cuatro tomas por ronda; el arroz tiene una toma por molino | [DOC] plan general |
| IVA | Todos los precios incluyen IVA | [DOC] ficha |
| Periodicidad de recolección | Perecederos: diaria. Carnes, lácteos, granos y procesados (incluida la panela): semanal. Arroz en molino: mensual | [DOC] ficha |
| Tipo de operación | Muestreo **no probabilístico**: no hay error muestral ni representatividad estadística formal | [DOC] ficha; [PÁGINA] catálogo 776 |
| Precios nominales | Pesos corrientes. Para comparar años hay que deflactar | Inferencia metodológica |
| Simbología de tendencia (semanal) | `---` < -20 %; `--` -10 a -20 %; `-` 0 a -10 %; `=`; `+` 0 a 10 %; `++` 10 a 20 %; `+++` > 20 %; `n.d.` | [PÁGINA] |

Implicación para "qué comprar y cuándo": las verduras, frutas y tubérculos (medición diaria) son los que tienen dinámica de corto plazo y estacionalidad marcada. Granos, carnes y procesados cambian más despacio. El MVP debería empezar por **unos 20 a 30 perecederos de alta rotación en Corabastos**.

---

## 5. Componente de abastecimiento (SIPSA_A)

| Recurso | URL | Formato | Granularidad | Historia | Estado |
|---|---|---|---|---|---|
| Página del componente | https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/componente-abastecimientos-1 | HTML | — | — | [PÁGINA] |
| **Series históricas abastecimiento 2013–2026** | https://www.dane.gov.co/files/operaciones/SIPSA/Series-historicas-abastecimiento-2013-2026.xlsx | XLSX | Mensual por mercado [SIN CONFIRMAR] | 2013–2026 | URL [PÁGINA] |
| Microdatos anonimizados 2026 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-Microdato-abastecimiento-2026.xlsx | XLSX | Registro de ingreso (producto, procedencia, toneladas) [DOC] | 2026 | URL [PÁGINA] |
| Microdatos 2025 / 2024 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-Microdato-abastecimiento-2025.xlsx · https://www.dane.gov.co/files/operaciones/SIPSA/anex-Microdato-abastecimiento-2024.xlsx | XLSX | Ídem | — | URL [PÁGINA] |
| Microdatos 2013–2023 | Patrón publicado: `https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/microdato-abastecimiento-AAAA.xlsx` (AAAA = 2013 a 2023; cada año enlazado en la página) | XLSX | Ídem | 2013–2023 | URLs [PÁGINA] |
| Ficha metodológica SIPSA_A (v3, 28-jun-2022) | https://bibliotecadoctecnica.dane.gov.co/static/documentos/DIMPE/SIPSA_A/SIPSA_A_Ficha%20metodol%c3%b3gica.pdf | PDF | — | — | [PÁGINA], abre: sí |

Contenido según la ficha [DOC]:
- Toneladas que ingresan a 29 mercados de 21 ciudades.
- Más de 170 alimentos en 8 grupos.
- Variables: grupo, cantidad (t) y **procedencia (departamento y municipio)**.
- Recolección diaria.
- Difusión: reporte diario, indicador semanal (de jueves a miércoles), boletín quincenal y boletín mensual.
- Series y microdatos desde **enero de 2013**.
- Los datos recientes son **provisionales** [PÁGINA].
- En las publicaciones, frutas, tubérculos y verduras se reportan por producto; el resto se agrupa en "otros grupos".

Utilidad: el volumen que entra a Corabastos (total y por producto) es una variable explicativa natural del precio, porque una caída de oferta suele anticipar alzas. Ojo con la **fuga de información**: el abastecimiento del mes *t* se publica alrededor del día 10 a 20 del mes siguiente, así que en el pronóstico solo pueden usarse sus rezagos.

---

## 6. Variables exógenas gratuitas

| Variable | Fuente | URL | Formato | Estado | Comentario |
|---|---|---|---|---|---|
| Índice ONI (El Niño / La Niña) | NOAA CPC | https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt (enlazado como "Data (Oceanic Nino Index)" en https://www.cpc.ncep.noaa.gov/data/indices/index.shtml) | Texto plano. Columnas esperadas `SEAS YR TOTAL ANOM` [SIN CONFIRMAR: no se abrió el archivo] | URL [PÁGINA] | Media móvil de 3 meses de Niño 3.4, base ERSSTv6. Relacionados en la misma página: insumo mensual https://www.cpc.ncep.noaa.gov/data/indices/detrend.nino34.ascii.txt y ONI relativo https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt. Dominio público como producto del gobierno de EE. UU. [SIN CONFIRMAR: no se leyó una declaración de licencia] |
| Festivos de Colombia | Paquete Python `holidays` (clase `CO`) | https://pypi.org/project/holidays/ · https://python-holidays.readthedocs.io/en/latest/_autosummary/holidays.countries.colombia.html | Paquete (pip) | [PÁGINA de búsqueda] | No requiere descarga de datos; incluye la Ley Emiliani (festivos trasladados a lunes) [SIN CONFIRMAR en el código] |
| IPC de alimentos (deflactor) | DANE, IPC | Página técnica: https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc/ipc-informacion-tecnica | XLSX (anexos) | **Enlace exacto del anexo [SIN CONFIRMAR]** | Necesario para pasar a pesos constantes. Los boletines siguen el patrón `files/operaciones/IPC/<mes><año>/bol-IPC-<mes><año>.pdf` (p. ej. https://www.dane.gov.co/files/operaciones/IPC/sep2026/bol-IPC-sep2026.pdf). El anexo de series por división no se localizó en esta sesión |
| Precipitación (opción A) | Open-Meteo, API histórica | Endpoint: `https://archive-api.open-meteo.com/v1/archive` con `latitude`, `longitude`, `start_date`, `end_date`, `daily=precipitation_sum`, `timezone` (obligatorio con variables diarias) y `format=csv`. Documentación: https://open-meteo.com/en/docs/historical-weather-api | JSON (por defecto), CSV o XLSX | Endpoint y parámetros [PÁGINA]; licencia exacta [SIN CONFIRMAR] | ERA5 desde 1940 (0,25°), ERA5-Land desde 1950 (0,1°). La página distingue planes "Non-Commercial" y "Commercial" pero no detalla la licencia; pide citar "Copernicus Climate Change Service". Al ser una consulta parametrizada (no un archivo fijo) se deja **fuera** del YAML del MVP |
| Precipitación (opción B) | CHIRPS v2.0 (UCSB/CHC), 0,05°, diaria desde 1981 | https://chc.ucsb.edu/data/chirps · ERDDAP NOAA: https://coastwatch.pfeg.noaa.gov/erddap/griddap/chirps20GlobalDailyP05.html | NetCDF/CSV (ERDDAP permite recortar) | [PÁGINA de búsqueda] | Más pesado; útil si se quiere lluvia en zonas productoras (Boyacá, Cundinamarca) |
| Precipitación (opción C) | IDEAM, DHIME | No se encontró un enlace de descarga directa estable | — | [SIN CONFIRMAR] | Requiere consulta interactiva; se descarta para el MVP |
| Precio del ACPM / diésel | MinEnergía / CREG / SICOM | No se encontró una serie pública descargable; solo noticias con precios puntuales | — | **No disponible** como serie limpia | Se descarta para el MVP. Además, el precio del ACPM en Colombia es **regulado** y cambia por escalones, así que aporta poca variación |

---

## 7. Prueba real de acceso desde este entorno

Comando ejecutado el 11-nov-2026 a las 06:09 UTC:

```
curl -sS -m 30 -o /dev/null -w "http=%{http_code} size=%{size_download}\n" <URL>
```

| URL probada | Resultado |
|---|---|
| https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-31oct06nov-2026.xlsx | `curl: (56) CONNECT tunnel failed, response 403` |
| https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt | `curl: (56) CONNECT tunnel failed, response 403` |
| https://www.datos.gov.co/api/views.json?limit=1 | `curl: (56) CONNECT tunnel failed, response 403` |

**Conclusión:** estos dominios **no son accesibles desde este entorno** (el proxy los bloquea). Siguiendo las instrucciones, no se buscaron mirrors ni cachés. Ningún archivo de datos se abrió con pandas, así que **ningún dato tiene la etiqueta [ARCHIVO]**.

Sí se pudo, con la herramienta de lectura web:
- Leer PDF del DANE (boletines y fichas).
- Comprobar que el anexo semanal XLSX del 31-oct al 6-nov-2026 **existe y responde con contenido binario**. Su contenido no se pudo interpretar.

La descarga real queda para el script `python -m mercado_al_dia.ingesta.descargar` en el PC del autor.

**Primera tarea de la fase 1:** abrir cada Excel y registrar las hojas, la fila de encabezado, las columnas, `Mercado.unique()`, el rango de `Fecha` y el número de productos de Corabastos. El objetivo es pasar a [ARCHIVO] lo que hoy está en [DOC] o [SIN CONFIRMAR].

---

## 8. Riesgos de datos

| # | Riesgo | Evidencia | Mitigación |
|---|---|---|---|
| R1 | **Cambio de formato entre años** | Las URLs cambian de carpeta en 2023; el nombre de 2023 es irregular ("Dic2023"); los microdatos pasan de 5 a 6 variables en 2024 [PÁGINA] | Un lector por "familia" de archivos, con prueba de esquema y una fila de encabezado detectada (no fija) |
| R2 | **Nombres de producto inconsistentes** | Variedades ("Papa capira", "Papa criolla limpia", ...), cambios de nombre y el código CPC solo en archivos recientes [SIN CONFIRMAR] | Tabla de equivalencias `producto_canonico` versionada a mano; usar CPC cuando exista |
| R3 | **Semanas o meses sin reporte** | Celdas vacías y guiones en los boletines [PÁGINA]; paro nacional (informe especial de mayo de 2021) y COVID-19 en 2020 [PÁGINA] | Calendario completo con huecos explícitos (NaN); variable indicadora de choque; no rellenar hacia adelante sin marcarlo |
| R4 | **Unidad no homogénea** | $/kg, $/unidad (huevos), $/litro; los diarios regionales usan unidad de empaque [DOC] | Usar solo series en $/kg para el MVP; guardar la unidad por producto |
| R5 | **Precios nominales** | Pesos corrientes de 2013 a 2026 | Deflactar con el IPC de alimentos (fuente por confirmar) o modelar en log con tendencia |
| R6 | **Muestra no probabilística** | Ficha SIPSA_P [DOC] | Presentar intervalos de pronóstico, no de "precisión muestral"; no extrapolar a otros mercados |
| R7 | **Abastecimiento provisional** | Boletín diario [PÁGINA] | Usar solo rezagos y la versión publicada en la fecha de cada pronóstico (*vintage*) |
| R8 | **Servicio SOAP antiguo** | Guía de 2020, WebLogic 11, Java 1.6, URL `http` [PÁGINA] | Usarlo solo como respaldo; puede apagarse sin aviso |
| R9 | **El archivo 2026 se sobrescribe cada mes en la misma URL** | Misma URL "2026" [PÁGINA] | El script guarda cada versión distinta con fecha (`--actualizar`) y no pisa la anterior |
| R10 | **Etiquetas erróneas en el sitio del DANE** | El enlace de sep-2022 tiene el título "Agosto 2022"; el de microdatos 2016 dice "2015" [PÁGINA] | Verificar el contenido (rango de fechas) y no fiarse del nombre |
| R11 | **Licencia y redistribución** | Términos del DANE: "Se autoriza el uso, aprovechamiento, transformación y análisis"; cita obligatoria "Fuente: Departamento Administrativo Nacional de Estadística: www.dane.gov.co" [PÁGINA]. Catálogo de microdatos: prohibida la reproducción electrónica para múltiples usuarios sin autorización escrita [PÁGINA] | **No subir `data/raw/` a GitHub**: se versiona el manifiesto, no los datos. En la web, publicar solo agregados y pronósticos derivados, con la cita del DANE |
| R12 | **Granularidad ambigua** | El diccionario dice "Precio Promedio Diario", pero el volumen de filas sugiere datos mensuales | Confirmar al abrir el archivo (fase 1) |
| R13 | **Mayorista ≠ consumidor** | Definición de la ficha | Declararlo en la web; nunca llamarlo "precio en tienda" |

---

## 9. Veredicto de viabilidad

**VIABLE CON CONDICIONES.**

- **Viable ya:** pronóstico **mensual** de precios mayoristas en **Corabastos** para los perecederos principales, con unos 13 años de historia (unas 160 observaciones por serie, de ene-2013 a sep-2026). Alcanza para SARIMAX con estacionalidad de 12 meses más ONI y calendario, y para LightGBM global entre productos. N-BEATS es posible en CPU con series cortas, pero su ventaja con unas 160 observaciones por serie es dudosa; mejor tratarlo como experimento.
- **Condición 1 (semanal):** la "canasta semanal" y las alertas para tenderos necesitan historia **semanal**. Para tenerla hay que confirmar en la fase 1 una de dos vías: (a) que el SOAP `promediosSipsaSemanaMadr` devuelve historia, o (b) reunir los anexos semanales año por año (unos 52 por año). Si ninguna funciona, las alertas semanales se construyen solo hacia adelante, acumulando desde ahora.
- **Condición 2 (Paloquemao):** solo entra si el Excel trae precios con `Mercado == "Bogotá, D.C., Paloquemao"` para una cantidad útil de productos.
- **Condición 3 (Madrid):** no hay dato propio. Se ofrece Corabastos como referencia regional, rotulada.
- **Condición 4 (licencia):** no redistribuir los datos crudos; citar al DANE.

**Fuente principal:** P1, las series históricas mensuales de precios mayoristas (Excel del DANE, 2013–2026).
**Respaldo:**
- P5 o P7, microdatos del catálogo 776 o datos.gov.co `gkqq-k3k5`, para validar los años 2013–2024.
- P6 (SOAP), para datos recientes y semanales.
- P2, anexos semanales, para la historia semanal reciente.

---

## 10. Qué debe descargar el autor

El script `python -m mercado_al_dia.ingesta.descargar` intenta bajar todo esto automáticamente; la lista vive en `config/fuentes.yaml`. **Si el script falla** (por ejemplo, si el DANE bloquea la descarga automática), descarga cada enlace con el navegador y guárdalo **con el nombre y en la carpeta indicados**. Luego corre el script otra vez: detecta el archivo, calcula su SHA-256 y lo registra en `data/manifest.json` como descarga "manual".

**Mínimo para el MVP: 13 archivos.**

| # | Enlace | Guardar como (dentro de `data/raw/`) |
|---|---|---|
| 1 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2013_2017.xlsx` |
| 2 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2018.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2018.xlsx` |
| 3 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2019.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2019.xlsx` |
| 4 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2020.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2020.xlsx` |
| 5 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2021.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2021.xlsx` |
| 6 | https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-2022.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2022.xlsx` |
| 7 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-Dic2023.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2023.xlsx` |
| 8 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-2024.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2024.xlsx` |
| 9 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-2025.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2025.xlsx` |
| 10 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-2026.xlsx | `sipsa/precios_mensual/sipsa_p_serie_mensual_2026.xlsx` |
| 11 | https://www.dane.gov.co/files/operaciones/SIPSA/Series-historicas-abastecimiento-2013-2026.xlsx | `sipsa/abastecimiento/sipsa_a_series_historicas_2013_2026.xlsx` |
| 12 | https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSASemanal-31oct06nov-2026.xlsx | `sipsa/precios_semanal/sipsa_p_semanal_2026-10-31_2026-11-06.xlsx` (muestra para conocer la estructura semanal) |
| 13 | https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt | `exogenas/noaa_oni.ascii.txt` |

Todas las URLs salen de páginas oficiales leídas en esta sesión. Que el archivo **abra** solo se comprobó para el #12 (la herramienta web recibió contenido binario); el resto se probará al correr el script.

**Opcionales (desactivados en `config/fuentes.yaml`; actívalos con `activo: true` cuando haga falta):**
- Microdatos de abastecimiento 2024–2026 (procedencia por municipio, para el ángulo de Madrid como origen).
- Boletín semanal en PDF del 19 al 25-sep-2026 (referencia visual).

**Fuera del script (por ahora):**
- Microdatos del catálogo 776: la descarga puede requerir registro. Descárgalos a mano desde https://microdatos.dane.gov.co/index.php/catalog/776/get-microdata hacia `data/raw/sipsa/microdatos_p/` y corre el script para registrarlos.
- datos.gov.co `gkqq-k3k5`: abre https://www.datos.gov.co/dataset/Sistema-de-Informaci-n-de-Precios-y-Abastecimiento/gkqq-k3k5, usa "Exportar" → CSV y guárdalo como `data/raw/sipsa/datos_gov_co/gkqq-k3k5.csv`.

---

## 11. Próximos pasos (fase 1)

1. Correr el script en el PC del autor y revisar `data/manifest.json`.
2. Inspeccionar cada Excel: hojas, encabezado, columnas, mercados, fechas y productos de Corabastos. Actualizar las etiquetas de este documento a [ARCHIVO].
3. Decidir sobre Paloquemao con el dato en la mano.
4. Probar el SOAP desde el PC con una sola llamada a `promediosSipsaSemanaMadr` y anotar si devuelve historia.
5. Localizar el anexo del IPC por divisiones (alimentos) para deflactar.

---

## 12. Fuentes consultadas en esta sesión

- Página SIPSA, boletín diario, boletín semanal, boletín mensual y series históricas, abastecimiento y servicio web: URLs de la sección 2.1 y de la sección 5.
- Guía del servicio web: https://www.dane.gov.co/files/investigaciones/agropecuario/sipsa/DANE-webservice-SIPSA.pdf
- Fichas: SIPSA_P (bibliotecadoctecnica, sección 2.1) y SIPSA_A (sección 5).
- Plan general SIPSA_P (sección 2.1).
- Boletines: diario del 21-oct-2026, semanal del 19 al 25-sep-2026 y mensual de sep-2026 (sección 3.1).
- Microdatos: https://microdatos.dane.gov.co/index.php/catalog/776, https://microdatos.dane.gov.co/index.php/catalog/776/data-dictionary, https://microdatos.dane.gov.co/catalog/645 (SIPSA_A 2013–2017, condiciones de acceso).
- Términos y condiciones del DANE: https://www.dane.gov.co/index.php/terrminos-y-condiciones-dane
- datos.gov.co: https://www.datos.gov.co/dataset/Sistema-de-Informaci-n-de-Precios-y-Abastecimiento/gkqq-k3k5
- Exógenas: https://www.cpc.ncep.noaa.gov/data/indices/index.shtml, https://pypi.org/project/holidays/, https://open-meteo.com/en/docs/historical-weather-api, https://chc.ucsb.edu/data/chirps

### Nota de verificación de exógenas

- **ONI:** la URL `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt` aparece publicada en la página índice del CPC [PÁGINA]. La descarga desde este entorno falló (403 del proxy), así que su contenido no se leyó.
- **Open-Meteo:** el endpoint y los parámetros salen de su documentación [PÁGINA]; no se hizo ninguna llamada.
- **Histórico semanal 2025:** página leída; 52 anexos XLSX con nombres irregulares (sección 2.2).

---

## Anexo — Confirmado leyendo los archivos (11-nov-2026)

El autor descargó las 13 fuentes sin errores. Aquí se abrieron 5 de los 11 Excel de precios mensuales
(2013–2017, 2018, 2022, 2026 y el boletín semanal) y el de abastecimiento; 2019–2021 y 2023–2025 no se
abrieron todavía.

**Cobertura de precios mensuales (confirmada):**

| Mercado (nombre exacto en los datos) | Productos por año | Años vistos | Meses |
|---|---|---|---|
| Bogotá, D.C., Corabastos | 170–190 | 2013–2018, 2022, 2026 | 12 de 12 (2026: ene–oct) |
| Bogotá, D.C., Paloquemao | 79–104 | 2013–2018, 2022, 2026 | 12 de 12 (2026: ene–oct) |
| Bogotá, D.C., Plaza Las Flores | 12–71 (crece con los años) | ídem | ídem |
| Bogotá, D.C., Plaza España | 30–47 | ídem | ídem |
| Bogotá, D.C., Frigorífico Guadalupe / Ble Ltda. | 32–40 (carnes) | ídem | ídem |
| Madrid (Cundinamarca) | **no existe** | — | — |

- **Paloquemao sí tiene precios**, con historia desde 2013: deja de ser "sin confirmar".
- **Madrid no aparece** en ningún año. Los mercados de Cundinamarca son Caparrapí, Nocaima y Villeta
  (1–3 productos) y Ubaté (39–50 productos, visto hasta 2018; ausente en 2022 y 2026).
- Unidad: la columna se llama "Precio promedio por kilogramo*" desde 2022 ("Precio" antes).

**Riesgo de formato confirmado: tres esquemas distintos.**

| Archivo | Hojas | Columnas |
|---|---|---|
| 2013–2017 | una por año (`1.1`…`1.5`) | Fecha, Grupo, Producto, Fuente, Precio |
| 2018 | una (`2018`) | Fecha, Grupo, Producto, Fuente, Precio |
| 2022 | una por mes (`Ene 22`…) | Fecha, Grupo, Producto, Mercado, Precio promedio por kilogramo* |
| 2026 | una (`2026`) + `Fuentes` + `CPC` | agrega Código CPC, Departamento, Municipio y sus códigos |

El lector de la fase 1 debe ubicar la fila de encabezado por nombre (no por posición), aceptar
`Fuente`/`Mercado` como la misma columna y unir todas las hojas. La hoja `CPC` de 2026 sirve para
normalizar nombres de producto entre años.

**Abastecimiento:** serie mensual por mercado desde ene-2013 y serie semanal por ciudad y grupo desde
la semana del 5-ene-2013 (confirmado en el archivo).
