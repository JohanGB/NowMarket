# docs/auditoria_independiente/

> **Congelado al estado `estado-auditado`; no se mantiene.**

Scripts y prueba con los que se hizo la auditoría independiente del 17-nov-2026
(informe: [`../auditoria_independiente.md`](../auditoria_independiente.md)). Reproducen los hallazgos sobre
el código de la etiqueta git `estado-auditado` (commit `3234e86`, versión 1.0.0).

- **No se actualizan** con el código posterior. Desde la v1.1 corregida, algunas de estas piezas ya no
  corresponden: por ejemplo, `datos.entrenamiento` dejó de ser la lista final de entrenamiento, y
  `test_auditoria_publicacion.py` fallaba a propósito con el código auditado. Las pruebas vivas están en
  `tests/test_auditoria.py`.
- **pytest no los recoge**: `pyproject.toml` limita la búsqueda a `tests/` y este directorio tiene un
  `conftest.py` que lo excluye también si se corre `pytest docs/`. Solo se ejecutan si se nombra el archivo.
- Para reproducir el informe original, use una copia de la etiqueta: `git worktree add ../auditado estado-auditado`.
