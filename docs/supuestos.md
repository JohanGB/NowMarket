# Supuestos

Fecha: 11-nov-2026. Cada supuesto indica cómo se va a comprobar. Si uno resulta falso, se registra el cambio en `decisiones.md`.

| # | Supuesto | Por qué lo asumimos | Cómo se comprueba |
|---|---|---|---|
| S1 | El **precio mayorista** de Corabastos sirve como señal de *dirección y estacionalidad* del precio al consumidor en Bogotá, no de su nivel | Los minoristas se abastecen en gran parte en las centrales mayoristas | No se puede comprobar con SIPSA. Se declara como limitación en la web y en el README |
| S2 | ✅ **Confirmado (fase 1).** Las series históricas mensuales tienen un registro por **mes × mercado × producto**. El precio es $/kg salvo huevos y bocadillo ($/unidad) y aceite, vinagre y jugo de frutas ($/litro), según la nota al pie del DANE | Diccionario de microdatos del catálogo 776 (variables `Fecha`, `Grupo`, `Producto`, `Mercado`, `Precio_promedio_por_kilogramo_`) y unas 55.000 filas por año | Abrir los 10 Excel en la fase 1 |
| S3 | El precio "medio" es la **media aritmética de las tomas** del periodo, con IVA incluido | Plan general y ficha SIPSA_P | No es verificable con los datos; se acepta la documentación oficial |
| S4 | ✅ **Confirmado (fase 1).** Los nombres son comparables entre años: solo 3 renombres en Corabastos 2013–2026 (`config/productos.yaml`) y una variante de mercado ("Ltda."/"Ltda,") | Práctica habitual; el DANE añadió el código CPC en 2024 | Tabla de equivalencias y conteo de series que se cortan |
| S5 | **Decisión del autor (11-nov-2026):** Corabastos es la **referencia para Bogotá y la Sabana**, incluido Madrid (Cundinamarca), por cercanía y porque la Sabana occidente abastece y se abastece de Bogotá | No hay mercado SIPSA en Cundinamarca | No es verificable. Se rotula siempre como "referencia de Corabastos" |
| S6 | Con unas 160 observaciones mensuales por serie (2013–2026) hay información suficiente para estimar estacionalidad anual y efecto ENSO | Regla práctica: al menos 10 ciclos estacionales | Validación cruzada temporal (*backtesting*) en la fase de modelos |
| S7 | El ONI y los festivos se conocen **sin fuga de información** en el momento del pronóstico | El ONI se publica con un mes de rezago; los festivos se conocen de antemano | Construir las variables con su fecha de publicación |
| S8 | ✅ **Confirmado (fase 1).** El equipo del autor basta: los 11 Excel (767.549 filas) se leen en unos 30 s; el panel de Bogotá ocupa 67.036 filas | Unos 20 a 40 MB de Excel en total (estimación); modelos clásicos y LightGBM en CPU | Medir la memoria al cargar todos los años |
| S9 | Los términos del DANE permiten **usar y transformar** los datos y publicar resultados derivados con cita | Términos y condiciones del DANE ("Se autoriza el uso, aprovechamiento, transformación y análisis") | Revisión de la licencia antes de publicar la web; no redistribuir los crudos |

## Supuestos nuevos de la fase 1

| # | Supuesto | Por qué lo asumimos | Cómo se comprueba |
|---|---|---|---|
| S10 | La **canasta de referencia** (`config/canasta.yaml`) representa el mercado de un hogar de 4 personas en un mes | Cantidades razonables elegidas por el proyecto; **no es la canasta oficial del DANE** | No se comprueba: se rotula como supuesto y el autor puede cambiar cantidades |
| S11 | Comparar con la **mediana de los 12 meses anteriores** es una buena vara para decir "barato" o "caro" | Resiste meses atípicos y se ajusta solo a la inflación del último año | Se revisa en la fase 2 contra la versión deflactada con el IPC de alimentos |
| S12 | El perfil estacional (media móvil 2×12 sobre el logaritmo) es **estable entre años** | Ciclos de siembra y lluvias se repiten | Validación con origen rodante: acierta 78,2 % de 1.644 casos frente a 73,7 % de la línea base |

## Supuestos de las fases 2 y 3

| # | Supuesto | Por qué lo asumimos | Cómo se comprueba |
|---|---|---|---|
| S13 | El precio del mes t se conoce a comienzos de t+1; el ONI de la temporada que termina en t−1, en t; el abastecimiento de t−1, a mediados de t | Calendarios de publicación del DANE y de la NOAA | Rezagos en `config/modelos.yaml`; prueba `test_caracteristicas_usan_exogenas_con_rezago` |
| S14 | Los errores de validación representan los futuros (base de la calibración CQR) | Supuesto de intercambiabilidad de la predicción conformal | Cobertura en la prueba (v1.1, ingenuo calibrado): 80,6–82,8 % (meta 80 %). Falla por producto (`models/registro/prueba_por_producto.csv`, ingenuo calibrado): papa criolla 68,6 % a 1 mes, 61,8 % a 2 y 69,7 % a 3; zanahoria 74,3 % a 1 mes, 64,7 % a 2 y 57,6 % a 3. La papa pastusa no falla (77,1 %, 85,3 % y 81,8 %) |
| S15 | Sumar los rangos de los productos da un rango conservador para la canasta | Equivale a suponer que todos suben o bajan a la vez | Declarado en la página; no se calcula la dependencia entre productos |
| S16 | Los sustitutos de `config/sustitutos.yaml` son intercambiables en la cocina | Criterio del autor, no estadístico | Editable; la página solo cambia productos con la misma unidad |
