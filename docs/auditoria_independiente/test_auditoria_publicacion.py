"""CONGELADO al estado `estado-auditado`; no se mantiene (ver README.md de esta carpeta). pytest no lo recoge.

Pruebas de la auditoría independiente (17-nov-2026): ¿usa el modelo algo que en el origen aún no existía?

No forman parte de tests/ (pytest no las recoge por defecto). Requieren un panel regenerado:
    set MAD_RAIZ=<raíz con data/procesado/precios_bogota.csv y data/raw>   (Windows)
    python -m pytest -q docs/auditoria_independiente/test_auditoria_publicacion.py

Calendario de publicación usado (evidencia en docs/auditoria_independiente.md, tarea 2):
- Precio SIPSA del mes t: publicado entre el día 6 y el 17 de t+1 ("Fecha de actualización" de los Excel
  2018–2023; el de 2026 bajado el 11-nov-2026 ya trae octubre). Momento del pronóstico τ(t) = día 6 de t+1.
- ONI de la temporada que termina en el mes m: publicado a comienzos de m+1 (oni.ascii.txt del 11-nov-2026
  ya trae ASO-2026). En τ(t) se conoce como mucho la temporada que termina en t (centrada en t−1).
- Abastecimiento del mes m: publicado hacia el día 6 de m+1 ("Fecha de actualización: 6 de noviembre de 2026"
  con octubre incluido). En τ(t) se conoce como mucho el mes t.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from mercado_al_dia.modelos import datos as md
from mercado_al_dia.modelos import familias

RAIZ = Path(os.environ.get("MAD_RAIZ", Path(__file__).resolve().parents[2]))
ORIGENES = ["2021-11", "2023-11", "2025-11"]


@pytest.fixture(scope="module")
def entorno():
    if not (RAIZ / "data" / "procesado" / "precios_bogota.csv").exists():
        pytest.fail(f"Falta {RAIZ}/data/procesado/precios_bogota.csv: regenere el panel y defina MAD_RAIZ")
    cfg = yaml.safe_load((RAIZ / "config" / "modelos.yaml").read_text(encoding="utf-8"))
    return cfg, md.cargar(RAIZ, cfg)


def publicado_hasta(d: md.Datos, t: pd.Period, cfg: dict, lista_fija: bool) -> md.Datos:
    """Lo que existía en τ(t): precios ≤ t, ONI centrado ≤ t−1, abastecimiento ≤ t."""
    v = copy.copy(d)
    v.logp = d.logp.loc[:t]
    v.oni = d.oni.loc[: t - 1]
    v.abastecimiento = d.abastecimiento.loc[:t]
    if not lista_fija:   # la regla de config/modelos.yaml aplicada con lo que había en t
        minimo = int(cfg.get("meses_minimos_entrenamiento", 120))
        v.entrenamiento = [p for p in v.logp.columns if v.logp[p].notna().sum() >= minimo]
    return v


@pytest.mark.parametrize("origen", ORIGENES)
def test_lista_de_entrenamiento_solo_con_lo_publicado(entorno, origen):
    """FALLA: la lista de productos de los modelos globales se elige con meses posteriores al origen."""
    cfg, d = entorno
    t = pd.Period(origen, "M")
    asi = publicado_hasta(d, t, cfg, lista_fija=False)
    sobran = sorted(set(d.entrenamiento) - set(asi.entrenamiento))
    faltan = sorted(set(asi.entrenamiento) - set(d.entrenamiento))
    assert not sobran and not faltan, (
        f"origen {origen}: {len(d.entrenamiento)} productos con la muestra completa frente a "
        f"{len(asi.entrenamiento)} con lo publicado hasta el origen; sobran {len(sobran)} (p. ej. {sobran[:3]}), "
        f"faltan {faltan[:5]}")


@pytest.mark.parametrize("origen", ORIGENES)
@pytest.mark.parametrize("clase", [familias.Ingenuo, familias.EstacionalAjustado, familias.PerfilEstacional,
                                   familias.Sarimax, familias.LightGBMGlobal])
def test_pronostico_identico_con_solo_lo_publicado(entorno, clase, origen):
    """Con la lista de productos fija, el pronóstico en t no cambia si se borra todo lo publicado después de τ(t)."""
    cfg, d = entorno
    t = pd.Period(origen, "M")
    asi = publicado_hasta(d, t, cfg, lista_fija=True)
    a, b = clase(cfg), clase(cfg)
    a.ajustar(d, t)
    b.ajustar(asi, t)
    pa = pd.DataFrame(a.predecir(d, t, d.evaluacion)).set_index(["pid", "h"]).sort_index()
    pb = pd.DataFrame(b.predecir(asi, t, d.evaluacion)).set_index(["pid", "h"]).sort_index()
    assert len(pa) and pa.index.equals(pb.index)
    np.testing.assert_allclose(pa.to_numpy(), pb.to_numpy(), rtol=0, atol=1e-9)
