# Ficha: N-BEATS (experimental, no desplegado)

**Modelo.** N-BEATS genérico (Oreshkin et al., 2020): 4 bloques de 3 capas de 128 neuronas, conexión
doblemente residual, ventana de 24 meses, salida de 3 horizontes × 3 cuantiles, pérdida de cuantiles.
Global (160 productos). Adam, tasa 0,001, 1.500 pasos, lotes de 256, semilla fija. JAX en CPU (unos
6–7 s por reentrenamiento); no hizo falta GPU.

**Resultado.** Peor que el ingenuo en los tres horizontes: −17 %, −15 % y −15 % en validación
(IC 90 % enteramente negativos). Sin calibrar, sus intervalos cubrían solo 42–52 % (demasiado seguros).

**Decisión.** No se despliega (principio de honestidad del modelo). Con 160 series de 166 meses no hay
datos suficientes para que una red profunda le gane a modelos que usan la estructura del problema
(temporada, exógenas). Se reintentaría con datos semanales (más observaciones) o con un ensamble.
