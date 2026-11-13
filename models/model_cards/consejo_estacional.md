# Ficha: consejo de temporada ("suele subir / bajar el próximo mes")

**Qué es.** Una regla estadística, no un modelo entrenado. Para cada producto de Corabastos se quita la
tendencia del logaritmo del precio con una media móvil centrada 2×12 y se promedia el residuo por mes del
calendario. El cambio típico de un mes al siguiente es la diferencia de esos promedios.

**Cuándo da consejo.** Si el cambio típico es de al menos 3 % y supera 2 errores estándar (error entre años
de cada mes, combinado sin correlación). Si no, no dice nada.

**Datos.** SIPSA, series históricas mensuales de precios mayoristas 2013–2026 (DANE), mercado Corabastos.
Pesos corrientes. Mínimo 5 años con tendencia calculable por mes.

**Validación (origen rodante, sin fuga).** Para cada mes *t* desde 2018-01 hasta 2026-09, el perfil se
recalcula solo con datos hasta *t* y se predice la dirección de *t* a *t+1*. Prueba automatizada:
`test_perfil_no_usa_datos_del_futuro`.

| Métrica | Valor |
|---|---|
| Casos con consejo | 1.644 en 104 productos |
| Acierto de dirección | **78,2 %** (IC 95 % de Wilson: 76,2 %–80,2 %) |
| Línea base: repetir la dirección del mismo par de meses del año anterior | 73,7 % |
| ¿Se muestra? | Sí (debe superar la línea base y el 55 %) |

Detalle por producto: `data/procesado/validacion_estacional.csv`.

**Limitaciones.**
- Predice la **dirección**, no el tamaño del cambio ni el precio. El pronóstico con intervalos es la fase 2.
- Los casos no son independientes: productos parecidos se mueven juntos y el intervalo de confianza es optimista.
- Supone que la temporada se repite. Choques como El Niño, paros o importaciones la rompen; el ONI entra en la fase 2.
- Es precio mayorista; en tienda el cambio llega atenuado y con rezago.

**Cuándo no usarlo.** En productos con pocos años de historia, en hierbas muy volátiles (cilantro, perejil)
cuyo error es grande, o para decidir compras grandes sin mirar el precio del día.
