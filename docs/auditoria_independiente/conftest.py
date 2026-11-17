"""Congelado al estado `estado-auditado`; no se mantiene. pytest no recoge estos archivos por descubrimiento
(`pytest`, `pytest docs/`); solo se ejecutan nombrándolos de forma explícita."""
collect_ignore_glob = ["test_*.py"]
