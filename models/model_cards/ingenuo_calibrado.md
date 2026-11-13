# Ficha: ingenuo calibrado, pronóstico a 2 y 3 meses (desplegado)

**Qué es.** Lo más probable es que el precio siga igual; el rango sale de los cambios históricos a
2 o 3 meses del mismo producto (últimos 10 años, solo datos hasta el origen), ensanchado con CQR para
cubrir el 80 % (0,021 en log a 2 meses; 0,020 a 3 meses).

**Por qué se despliega.** En validación, ningún modelo (LightGBM, SARIMAX, N-BEATS) lo superó con una
mejora significativa a 2 o 3 meses (regla de `config/modelos.yaml`).

| Prueba | 2 meses | 3 meses |
|---|---|---|
| Error típico de la mediana | 16,0 % | 20,2 % |
| Cobertura 10–90 | 83,0 % | 82,6 % |
| Ancho medio del rango | 75,5 % | 102,5 % |

**Límite.** Los rangos son anchos: a 3 meses el precio puede duplicarse o caer a la mitad en productos
volátiles. En la prueba, LightGBM fue mejor también en estos horizontes; se reevalúa en la próxima
ventana de validación (D-024).
