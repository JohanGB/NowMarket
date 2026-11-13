"""Minería de precios: qué productos se mueven juntos, sustitutos y cambios de nivel.

1. **Movimiento conjunto.** Para cada producto con al menos 10 años de historia se toma el
   cambio mensual del log-precio, se le resta su promedio por mes del calendario (para que la
   temporada común no infle la relación) y se calcula la correlación entre pares con los meses
   que ambos tienen. Agrupamiento jerárquico (enlace promedio, distancia 1 − ρ); el número de
   grupos se elige por silueta entre 4 y 15.
2. **Sustitutos.** Los define el autor en ``config/sustitutos.yaml`` (criterio de uso en la
   cocina, no estadístico). La minería solo informa si se mueven juntos: un sustituto muy
   correlacionado ahorra poco cuando ambos suben a la vez.
3. **Cambios de nivel.** PELT (Killick et al., 2012) sobre el log-precio desestacionalizado,
   con penalización tipo BIC. Como los precios son muy persistentes, PELT "ve" saltos aunque no
   los haya (la revisión independiente midió 75–83 % de falsos positivos con series simuladas).
   Por eso un cambio solo se muestra si supera el percentil 95 de lo que el mismo detector
   encuentra en 200 series simuladas SIN cambio de nivel (AR(1) ajustado a cada producto):
   así la tasa de falsas alarmas queda cerca de 5 % por producto. Es descriptivo, no causal.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Grupos:
    etiqueta: dict[str, int]                  # producto -> grupo
    silueta: float
    k: int
    vecinos: dict[str, list[tuple[str, float]]]   # producto -> 3 más correlacionados (ρ)
    correlacion: pd.DataFrame


def retornos_desestacionalizados(logp: pd.DataFrame) -> pd.DataFrame:
    r = logp.diff()
    mes = r.index.month
    return r - r.groupby(mes).transform("mean")


def agrupar(logp: pd.DataFrame, minimo_meses: int = 120, min_comunes: int = 60) -> Grupos:
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    from sklearn.metrics import silhouette_score

    cols = [c for c in logp.columns if logp[c].notna().sum() >= minimo_meses]
    r = retornos_desestacionalizados(logp[cols])
    rho = r.corr(min_periods=min_comunes).fillna(0.0)
    m = rho.to_numpy(copy=True)
    np.fill_diagonal(m, 1.0)
    rho = pd.DataFrame(m, index=rho.index, columns=rho.columns)
    dist = np.clip(1 - m, 0, None)
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2
    Z = linkage(squareform(dist, checks=False), method="average")
    mejor = (-1.0, 1, np.ones(len(cols), dtype=int))
    for k in range(min(4, len(cols) - 1), min(16, len(cols))):
        et = fcluster(Z, k, criterion="maxclust")
        if len(set(et)) < 2:
            continue
        s = silhouette_score(dist, et, metric="precomputed")
        if s > mejor[0]:
            mejor = (s, k, et)
    s, k, et = mejor
    vecinos = {}
    for c in cols:
        orden = rho[c].drop(c).sort_values(ascending=False).head(3)
        vecinos[c] = [(o, float(v)) for o, v in orden.items()]
    return Grupos(dict(zip(cols, map(int, et))), float(s), int(k), vecinos, rho)


@dataclass
class CambioNivel:
    producto: str
    fecha: str                 # primer mes del nivel nuevo
    cambio: float              # diferencia de nivel (fracción) entre el segmento anterior y el nuevo
    segmentos: int


def desestacionalizar(serie: pd.Series) -> pd.Series:
    s = serie.dropna()
    return s - s.groupby(s.index.month).transform("mean")


def _ultimo_cambio(x: np.ndarray, minimo_segmento: int) -> tuple[int, float, int] | None:
    """(posición, cambio de nivel en log, número de segmentos) del último corte de PELT."""
    import ruptures as rpt

    sigma2 = float(np.var(np.diff(x))) / 2                     # ruido de un mes a otro
    pen = 2 * math.log(len(x)) * max(sigma2, 1e-6) * 3
    cortes = rpt.Pelt(model="l2", min_size=minimo_segmento).fit(x.reshape(-1, 1)).predict(pen=pen)
    if len(cortes) < 2:
        return None
    c_ini, c = (cortes[-3] if len(cortes) >= 3 else 0), cortes[-2]
    return c, float(x[c:].mean() - x[c_ini:c].mean()), len(cortes)


def cambios_de_nivel(logp: pd.DataFrame, productos: list[str], minimo_segmento: int = 6) -> dict[str, CambioNivel | None]:
    salida = {}
    for p in productos:
        s = desestacionalizar(logp[p])
        r = _ultimo_cambio(s.to_numpy(), minimo_segmento) if len(s) >= 36 else None
        salida[p] = CambioNivel(p, str(s.index[r[0]]), float(math.expm1(r[1])), r[2]) if r else None
    return salida


def umbral_nulo(logp: pd.DataFrame, productos: list[str], recientes: int, simulaciones: int = 200,
                nivel: float = 0.95, semilla: int = 0, minimo_segmento: int = 6) -> dict[str, float]:
    """Percentil `nivel` del |cambio| reciente que el detector reporta en series AR(1) sin cambio de nivel."""
    rng = np.random.default_rng(semilla)
    salida = {}
    for p in productos:
        x = desestacionalizar(logp[p]).to_numpy()
        if len(x) < 36:
            salida[p] = float("inf")
            continue
        z = x - x.mean()
        phi = float(np.clip(np.dot(z[1:], z[:-1]) / np.dot(z[:-1], z[:-1]), -0.99, 0.99))
        sd = float(np.std(z[1:] - phi * z[:-1]))
        n, maximos = len(x), []
        for _ in range(simulaciones):
            e = rng.normal(0, sd, n + 50)
            y = np.zeros(n + 50)
            for t in range(1, n + 50):
                y[t] = phi * y[t - 1] + e[t]
            y = y[50:]
            r = _ultimo_cambio(y, minimo_segmento)
            maximos.append(abs(math.expm1(r[1])) if r and r[0] > n - recientes else 0.0)
        salida[p] = float(np.quantile(maximos, nivel))
    return salida
