# data/raw: datos crudos (inmutables)

Aquí van los archivos **tal como los publica la fuente oficial**, sin abrirlos ni guardarlos de nuevo con Excel.

## Reglas

1. **Nunca se edita un archivo de esta carpeta.** Ni para corregir un dato ni para "guardar como". Toda limpieza se hace en código y su resultado va a otra carpeta (p. ej. `data/interim/` o `data/processed/`).
2. Cada archivo queda registrado en `data/manifest.json` con su URL, fecha y hora de descarga (UTC), tamaño y SHA-256.
3. Si el DANE publica una versión nueva en la misma URL, se guarda **otro** archivo con el sufijo `__AAAAMMDD`. La versión anterior no se borra.
4. Esta carpeta **no se sube a git** (ver `.gitignore` y `docs/decisiones.md`, D-006). El manifiesto sí se sube.

## Cómo llenarla

Desde la raíz del proyecto:

```
pip install -e .
python -m mercado_al_dia.ingesta.descargar
```

Si una descarga falla, el script muestra el enlace exacto y la ruta donde debe guardarse el archivo. Bájalo con el navegador, guárdalo **con ese nombre y en esa carpeta**, y vuelve a correr el script. El script lo registra en el manifiesto con origen `manual`.

Si el script avisa con `ALERTA` que un archivo no coincide con su SHA-256, alguien lo modificó. Recupera el original volviendo a descargarlo; no edites el manifiesto a mano.

## Estructura prevista

```
data/raw/
  sipsa/
    precios_mensual/        series históricas SIPSA_P, un archivo por año (2013-2026)
    precios_semanal/        anexos de boletines semanales
    abastecimiento/         series históricas SIPSA_A
    abastecimiento_microdatos/  (opcional) microdatos anonimizados SIPSA_A
    microdatos_p/           (manual) microdatos SIPSA_P, catálogo 776
    datos_gov_co/           (manual) exportaciones de datos.gov.co
  exogenas/
    noaa_oni.ascii.txt      índice ONI (NOAA CPC)
```

Cita obligatoria de los datos del DANE: "Fuente: Departamento Administrativo Nacional de Estadística: www.dane.gov.co".
