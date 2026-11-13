"""Origen rodante, selección en validación, calibración conformal y prueba única.

Protocolo (config/modelos.yaml):
1. Validación (2021-11 a 2023-10): cada familia pronostica desde cada origen con modelos
   reentrenados cada 12 orígenes, solo con objetivos observados hasta el origen. Solo se
   conservan pronósticos cuyo mes objetivo cae dentro de la validación.
2. Calibración conformal (CQR, Romano et al. 2019): con los errores de validación se calcula,
   por familia y horizonte, cuánto ensanchar el intervalo 10–90 para cubrir el 80 %.
3. Selección: por horizonte gana la familia con menor pérdida de cuantiles en validación,
   siempre que supere a la mejor línea base con una mejora cuyo IC 90 % (bootstrap de
   orígenes) quede por encima de cero; si ninguna lo logra, se despliega la mejor línea base.
4. Prueba (2023-11 a 2026-09): se ejecuta una sola vez, después de fijar 1–3, y se reporta.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import metricas
from .datos import Datos


def origenes(desde: str, hasta: str) -> pd.PeriodIndex:
    return pd.period_range(pd.Period(desde, "M"), pd.Period(hasta, "M"), freq="M")


def rodar(modelo, datos: Datos, orig: pd.PeriodIndex, productos: list[str], reajuste: int,
          objetivo_hasta: pd.Period) -> pd.DataFrame:
    filas, ultimo_ajuste = [], None
    for t in orig:
        if ultimo_ajuste is None or (t - ultimo_ajuste).n >= reajuste:
            modelo.ajustar(datos, t)
            ultimo_ajuste = t
        for f in modelo.predecir(datos, t, productos):
            objetivo = t + f["h"]
            if objetivo > objetivo_hasta or objetivo > datos.ultimo:
                continue
            y = datos.logp.at[objetivo, f["pid"]]
            if pd.isna(y):
                continue
            filas.append(f | {"origen": str(t), "objetivo": str(objetivo), "y": y,
                              "base": datos.logp.at[t, f["pid"]], "modelo": modelo.nombre})
    return pd.DataFrame(filas)


def cqr(pred: pd.DataFrame, cobertura: float) -> dict[int, float]:
    """Ensanche por horizonte (en log) para que el intervalo 10–90 cubra `cobertura` (CQR)."""
    salida = {}
    for h, g in pred.groupby("h"):
        e = np.maximum(g["q10"] - g["y"], g["y"] - g["q90"]).to_numpy()
        n = len(e)
        nivel = min(1.0, math.ceil((n + 1) * cobertura) / n)
        salida[int(h)] = float(np.quantile(e, nivel, method="higher"))
    return salida


def aplicar_cqr(pred: pd.DataFrame, ajuste: dict[int, float]) -> pd.DataFrame:
    p = pred.copy()
    a = p["h"].map(ajuste).fillna(0.0)
    p["q10"], p["q90"] = p["q10"] - a, p["q90"] + a
    return p


def tabla_metricas(pred: pd.DataFrame, cfg: dict, escala: dict) -> pd.DataFrame:
    filas = []
    for (m, h), g in pred.groupby(["modelo", "h"]):
        filas.append({"modelo": m, "h": int(h), **metricas.resumen(g, cfg["cuantiles"], escala)})
    return pd.DataFrame(filas).sort_values(["h", "pinball"])


def seleccionar(tabla: pd.DataFrame, pred: pd.DataFrame, lineas_base: list[str], cfg: dict) -> dict[int, dict]:
    """Por horizonte: la familia de menor pérdida que mejore de forma significativa a la mejor línea base."""
    from . import metricas

    reps, semilla = int(cfg.get("bootstrap_repeticiones", 2000)), int(cfg["semilla"])
    eleccion = {}
    for h, g in tabla.groupby("h"):
        g = g.set_index("modelo").sort_values("pinball")
        base = g.loc[g.index.isin(lineas_base), "pinball"].idxmin()
        pb = pred[(pred["h"] == h) & (pred["modelo"] == base)]
        candidatos = []
        for m in g.index:
            if m in lineas_base:
                continue
            mej, lo, hi = metricas.bootstrap_mejora(pred[(pred["h"] == h) & (pred["modelo"] == m)], pb,
                                                    cfg["cuantiles"], reps, semilla, int(cfg.get("bootstrap_bloque", 1)))
            candidatos.append({"modelo": m, "pinball": float(g.at[m, "pinball"]), "mejora": mej,
                               "ic90": [lo, hi], "significativa": lo > 0})
        validos = [c for c in candidatos if c["significativa"]]
        ganador = min(validos, key=lambda c: c["pinball"])["modelo"] if validos else base
        eleccion[int(h)] = {"modelo": ganador, "mejor_linea_base": base,
                            "pinball_base": float(g.at[base, "pinball"]), "candidatos": candidatos}
    return eleccion


def huella(raiz: Path, cfg: dict) -> dict:
    """Huellas para reproducir: configuración, datos crudos (manifiesto) y versión del código."""
    from .. import __version__
    man = raiz / "data" / "manifest.json"
    datos = json.loads(man.read_text(encoding="utf-8")).get("archivos", {}) if man.exists() else {}
    sha_datos = hashlib.sha256("".join(sorted(v["sha256"] for v in datos.values())).encode()).hexdigest()
    return {"version": __version__, "sha256_config": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
            "sha256_datos": sha_datos, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
