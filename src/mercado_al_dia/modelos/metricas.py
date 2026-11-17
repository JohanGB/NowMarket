"""Métricas de pronóstico. Todas en escala relativa para poder promediar productos de precios muy
distintos y no confundir inflación con error: pérdida de cuantiles y MASE sobre el logaritmo del
precio; MAE como porcentaje del precio real."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def pinball(y: np.ndarray, q: np.ndarray, tau: float) -> np.ndarray:
    d = y - q
    return np.maximum(tau * d, (tau - 1) * d)


def resumen(pred: pd.DataFrame, cuantiles: list[float], escala: dict[str, float]) -> dict:
    """pred: columnas pid, h, y (log real), q10, q50, q90 (log), base (log del origen)."""
    y = pred["y"].to_numpy()
    cols = [f"q{int(round(t * 100))}" for t in cuantiles]
    perd = np.mean([pinball(y, pred[c].to_numpy(), t) for c, t in zip(cols, cuantiles)], axis=0)
    real, med = np.exp(y), np.exp(pred["q50"].to_numpy())
    err = np.abs(real - med)
    esc = pred["pid"].map(escala).to_numpy()
    cambio_pred = pred["q50"].to_numpy() - pred["base"].to_numpy()
    con_direccion = np.abs(cambio_pred) > 1e-12          # el ingenuo no predice dirección
    dentro = (y >= pred[cols[0]].to_numpy()) & (y <= pred[cols[-1]].to_numpy())
    return {
        "n": int(len(pred)),
        "pinball": float(np.mean(perd)),                  # pérdida de cuantiles media (log)
        "crps_aprox": float(2 * np.mean(perd)),           # CRPS aproximado con 3 cuantiles
        "mae_pct": float(np.mean(err / real)),            # error absoluto relativo de la mediana
        "rmse_log": float(np.sqrt(np.mean((y - pred["q50"].to_numpy()) ** 2))),
        "mase": float(np.mean(np.abs(y - pred["q50"].to_numpy()) / esc)),
        "cobertura": float(np.mean(dentro)),
        "ancho_pct": float(np.mean(np.exp(pred[cols[-1]]) / np.exp(pred[cols[0]]) - 1)),
        "acierto_direccion": (float(np.mean(np.sign(y - pred["base"].to_numpy())[con_direccion]
                                            == np.sign(cambio_pred)[con_direccion])) if con_direccion.any() else None),
    }


def escala_mase(logp: pd.DataFrame, hasta: pd.Period) -> dict[str, float]:
    """Error medio del ingenuo de 1 mes, en logaritmo, con datos hasta `hasta` (sin mirar el futuro)."""
    d = logp.loc[:hasta].diff().abs()
    return {c: float(d[c].mean()) if d[c].notna().any() else float("nan") for c in d.columns}


def perdida_por_caso(pred: pd.DataFrame, cuantiles: list[float]) -> np.ndarray:
    cols = [f"q{int(round(t * 100))}" for t in cuantiles]
    y = pred["y"].to_numpy()
    return np.mean([pinball(y, pred[c].to_numpy(), t) for c, t in zip(cols, cuantiles)], axis=0)


def indices_bloques(n: int, bloque: int, repeticiones: int, rng: np.random.Generator) -> np.ndarray:
    """Índices de un bootstrap de bloques circulares (Politis y Romano, 1992): matriz repeticiones × n.

    Cada bloque son ``bloque`` orígenes consecutivos y da la vuelta al final de la serie, así todos los
    orígenes tienen la misma probabilidad de salir. Corrección (c) de la auditoría: la versión anterior
    (bloques móviles sin vuelta) sorteaba menos los primeros y últimos orígenes y desplazaba el IC.
    Con ``bloque`` = 1 es el bootstrap iid de orígenes.
    """
    b = max(1, int(bloque))
    if b == 1:
        return rng.integers(0, n, size=(repeticiones, n))
    inicios = rng.integers(0, n, size=(repeticiones, math.ceil(n / b)))
    return ((inicios[:, :, None] + np.arange(b)) % n).reshape(repeticiones, -1)[:, :n]


def bootstrap_mejora(a: pd.DataFrame, b: pd.DataFrame, cuantiles: list[float], repeticiones: int,
                     semilla: int, bloque: int = 1) -> tuple[float, float, float]:
    """Mejora relativa de `a` sobre `b` (1 − pérdida_a/pérdida_b) con IC 90 % por bootstrap de orígenes.

    Se remuestrean orígenes completos (no casos sueltos) porque los productos de un mismo mes
    comparten choques y no son independientes. Con ``bloque`` > 1 se remuestrean bloques circulares de
    orígenes consecutivos, que además respetan la autocorrelación entre meses (``bootstrap_bloque`` en
    config/modelos.yaml; D-024 y D-030).
    """
    k = ["pid", "origen", "h"]
    m = a.assign(la=perdida_por_caso(a, cuantiles))[k + ["la"]].merge(
        b.assign(lb=perdida_por_caso(b, cuantiles))[k + ["lb"]], on=k)
    por_origen = m.groupby("origen")[["la", "lb"]].sum().sort_index()      # orden cronológico (AAAA-MM)
    la, lb = por_origen["la"].to_numpy(), por_origen["lb"].to_numpy()
    idx = indices_bloques(len(la), bloque, repeticiones, np.random.default_rng(semilla))
    mejoras = 1 - la[idx].sum(axis=1) / lb[idx].sum(axis=1)
    return float(1 - la.sum() / lb.sum()), float(np.quantile(mejoras, 0.05)), float(np.quantile(mejoras, 0.95))
