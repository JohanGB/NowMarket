"""Familias de modelos. Todas comparten la misma interfaz y la misma regla sin fuga:

- ``ajustar(datos, hasta)``: entrena solo con objetivos observados hasta el mes ``hasta``.
- ``predecir(datos, origen)``: usa solo precios hasta ``origen`` y exógenas ya publicadas.
Devuelven filas (pid, h, q10, q50, q90) en logaritmo del precio del mes ``origen + h``.

Líneas base (obligatorias, D-022):
  ingenuo            el precio no cambia; intervalos con los cambios históricos a h meses.
  estacional_ajustado el cambio de t a t+h repite el del mismo par de meses del año anterior.
  perfil_estacional  el método de la fase 1 (perfil 2×12) llevado a pronóstico.
Modelos:
  sarimax            SARIMA(1,1,1)(0,1,1)12 por producto, con ONI rezagado 5 meses.
  lightgbm           global (todos los productos), directo por horizonte, regresión de cuantiles.
  nbeats             ver nbeats.py (experimental, requiere JAX).
"""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd

from .. import analisis
from .datos import Datos, productos_entrenamiento

COLS = ["q10", "q50", "q90"]


def _filas(pid, h, base, q) -> dict:
    q = np.sort(np.asarray(q, dtype=float))     # evita cuantiles cruzados
    return {"pid": pid, "h": h, "q10": base + q[0], "q50": base + q[1], "q90": base + q[2]}


class _Base:
    nombre = "base"
    familia = "linea_base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.h = list(cfg["horizontes"])
        self.tau = list(cfg["cuantiles"])

    def ajustar(self, datos: Datos, hasta: pd.Period) -> None:   # las líneas base no se entrenan
        pass

    def _hist(self, datos: Datos, origen: pd.Period) -> pd.DataFrame:
        return datos.logp.loc[:origen]


class Ingenuo(_Base):
    nombre = "ingenuo"

    def predecir(self, datos: Datos, origen: pd.Period, productos: list[str]) -> list[dict]:
        L = self._hist(datos, origen)
        salida = []
        for pid in productos:
            s = L[pid]
            if pd.isna(s.iloc[-1]):
                continue
            for h in self.h:
                cambios = (s.shift(-h) - s).dropna().iloc[-120:]
                if len(cambios) < 24:
                    continue
                q = np.quantile(cambios, self.tau)
                q[1] = 0.0                                   # la mediana del ingenuo es "no cambia"
                salida.append(_filas(pid, h, s.iloc[-1], q))
        return salida


class EstacionalAjustado(_Base):
    nombre = "estacional_ajustado"

    def predecir(self, datos, origen, productos):
        L = self._hist(datos, origen)
        salida = []
        for pid in productos:
            s = L[pid]
            if pd.isna(s.iloc[-1]):
                continue
            for h in self.h:
                senal = s.shift(12 - h) - s.shift(12)              # cambio del año anterior (conocido en t)
                real = s.shift(-h) - s
                err = (real - senal).dropna().iloc[-120:]
                x = senal.iloc[-1]
                if pd.isna(x) or len(err) < 24:
                    continue
                salida.append(_filas(pid, h, s.iloc[-1], x + np.quantile(err, self.tau)))
        return salida


class PerfilEstacional(_Base):
    nombre = "perfil_estacional"

    def predecir(self, datos, origen, productos):
        L = self._hist(datos, origen)
        salida = []
        for pid in productos:
            s = L[pid]
            if pd.isna(s.iloc[-1]):
                continue
            serie = {p.year * 12 + p.month - 1: math.exp(v) for p, v in s.dropna().items()}
            perfil = analisis.perfil(serie, anios_minimos=5)
            if perfil is None:
                continue
            ef = np.array(perfil.efecto)
            meses = np.array([p.month - 1 for p in s.index])
            for h in self.h:
                senal = pd.Series(ef[(meses + h) % 12] - ef[meses], index=s.index)
                err = ((s.shift(-h) - s) - senal).dropna().iloc[-120:]
                if len(err) < 24:
                    continue
                salida.append(_filas(pid, h, s.iloc[-1], senal.iloc[-1] + np.quantile(err, self.tau)))
        return salida


class Sarimax(_Base):
    nombre = "sarimax"
    familia = "estadistico"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.resultados: dict[str, object] = {}
        self.fallas: list[str] = []

    def _exog(self, datos: Datos, indice: pd.PeriodIndex) -> np.ndarray:
        r = int(self.cfg["exogenas"]["oni_rezago_sarimax"])
        return datos.oni.reindex(indice - r).to_numpy().reshape(-1, 1)

    def ajustar(self, datos, hasta):
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        self.resultados.clear()
        p = self.cfg["sarimax"]
        for pid in datos.evaluacion:
            y = datos.logp.loc[:hasta, pid]
            y = y.loc[y.first_valid_index():]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    m = SARIMAX(y.to_numpy(), exog=self._exog(datos, y.index), order=tuple(p["orden"]),
                                seasonal_order=tuple(p["orden_estacional"]))
                    self.resultados[pid] = (m.fit(disp=False, maxiter=200), y.index[0])
            except Exception as e:                                  # noqa: BLE001
                self.fallas.append(f"{pid} {hasta}: {type(e).__name__}")

    def predecir(self, datos, origen, productos):
        salida = []
        z = 1.2815515655446004                                     # cuantil 0,9 de la normal
        for pid in productos:
            if pid not in self.resultados or pd.isna(datos.logp.at[origen, pid]):
                continue
            res, inicio = self.resultados[pid]
            y = datos.logp.loc[inicio:origen, pid]
            futuro = pd.period_range(origen + 1, periods=max(self.h), freq="M")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = res.apply(y.to_numpy(), exog=self._exog(datos, y.index))
                    f = r.get_forecast(steps=max(self.h), exog=self._exog(datos, futuro))
                    media, se = f.predicted_mean, np.sqrt(f.var_pred_mean)
            except Exception as e:                                  # noqa: BLE001
                self.fallas.append(f"{pid} {origen}: {type(e).__name__}")
                continue
            base = y.iloc[-1]
            for h in self.h:
                m, s = media[h - 1] - base, se[h - 1]
                salida.append(_filas(pid, h, base, [m - z * s, m, m + z * s]))
        return salida


# ------------------------------------------------------------------ LightGBM global

def caracteristicas(datos: Datos, h: int, cfg: dict, productos: list[str] | None = None) -> pd.DataFrame:
    """Tabla larga (mes, pid) con variables conocidas en el origen y el objetivo y = log p(t+h) − log p(t).

    ``productos``: columnas de la tabla (por defecto, los candidatos de ``datos.entrenamiento``). Las
    variables de cada producto solo dependen de su propia serie; el código de grupo, de los grupos presentes.
    """
    productos = list(datos.entrenamiento if productos is None else productos)
    L = datos.logp[productos]
    dif = L.diff()
    partes = {
        "r1": L - L.shift(1), "r3": L - L.shift(3), "r6": L - L.shift(6), "r12": L - L.shift(12),
        "dev12": L - L.rolling(12, min_periods=8).mean(),
        "vol12": dif.rolling(12, min_periods=8).std(),
        "anio_ant": L.shift(12 - h) - L.shift(12),
        "anio_ant2": L.shift(24 - h) - L.shift(24),
        "y": L.shift(-h) - L,
    }
    largo = pd.concat({k: v.stack(future_stack=True) for k, v in partes.items()}, axis=1)
    largo.index.names = ["mes", "pid"]
    largo = largo.reset_index()
    ex = cfg["exogenas"]
    meses = pd.PeriodIndex(largo["mes"], freq="M")
    oni = datos.oni
    largo["oni"] = oni.reindex(meses - int(ex["oni_rezago"])).to_numpy()
    largo["d_oni"] = largo["oni"] - oni.reindex(meses - int(ex["oni_rezago"]) - 3).to_numpy()
    a, ra = datos.abastecimiento, int(ex["abastecimiento_rezago"])
    largo["abast_anual"] = a.reindex(meses - ra).to_numpy() - a.reindex(meses - ra - 12).to_numpy()
    largo["mes_objetivo"] = ((meses.month - 1 + h) % 12).astype(int)
    largo["mes_origen"] = (meses.month - 1).astype(int)
    grupos = sorted(set(datos.grupos[p] for p in productos))
    largo["grupo"] = largo["pid"].map({p: grupos.index(datos.grupos[p]) for p in productos})
    largo = largo[L.stack(future_stack=True).notna().to_numpy()]          # el precio del origen existe
    return largo


VARIABLES = ["r1", "r3", "r6", "r12", "dev12", "vol12", "anio_ant", "anio_ant2", "oni", "d_oni",
             "abast_anual", "mes_objetivo", "mes_origen", "grupo"]


class LightGBMGlobal(_Base):
    nombre = "lightgbm"
    familia = "aprendizaje_automatico"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.tablas = {}
        self.modelos = {}
        self.productos: list[str] = []                 # productos de entrenamiento del último ajuste
        self.productos_por_ajuste: dict[str, int] = {}

    def _tabla(self, datos, h):
        if h not in self.tablas:
            columnas = sorted(set(self.productos) | set(datos.evaluacion))
            self.tablas[h] = caracteristicas(datos, h, self.cfg, columnas)
        return self.tablas[h]

    def ajustar(self, datos, hasta):
        import lightgbm as lgb

        # Lista elegida solo con precios hasta `hasta` (corrección (a) de la auditoría).
        productos = productos_entrenamiento(datos.logp, hasta, int(self.cfg["meses_minimos_entrenamiento"]),
                                            datos.entrenamiento)
        if productos != self.productos:
            self.productos, self.tablas = productos, {}
        self.productos_por_ajuste[str(hasta)] = len(productos)
        self.modelos.clear()
        for h in self.h:
            t = self._tabla(datos, h)
            ok = (t["mes"] + h <= hasta) & t["y"].notna() & t["pid"].isin(productos)   # objetivo observado hasta `hasta`
            X, y = t.loc[ok, VARIABLES], t.loc[ok, "y"]
            for tau in self.tau:
                m = lgb.LGBMRegressor(objective="quantile", alpha=tau, random_state=int(self.cfg["semilla"]),
                                      n_jobs=2, verbose=-1, deterministic=True, force_row_wise=True,
                                      **self.cfg["lightgbm"])
                m.fit(X, y, categorical_feature=["grupo"])
                self.modelos[(h, tau)] = m

    def predecir(self, datos, origen, productos):
        salida = []
        for h in self.h:
            t = self._tabla(datos, h)
            fila = t[(t["mes"] == origen) & t["pid"].isin(productos)]
            if fila.empty:
                continue
            q = np.column_stack([self.modelos[(h, tau)].predict(fila[VARIABLES]) for tau in self.tau])
            for pid, qi in zip(fila["pid"], q):
                salida.append(_filas(pid, h, datos.logp.at[origen, pid], qi))
        return salida

    def importancia(self) -> dict[str, float]:
        tot = {}
        for (h, tau), m in self.modelos.items():
            if tau == 0.5:
                g = m.booster_.feature_importance("gain")
                for v, x in zip(VARIABLES, g / g.sum()):
                    tot[v] = tot.get(v, 0) + x / len(self.h)
        return dict(sorted(tot.items(), key=lambda kv: -kv[1]))


LINEAS_BASE = [Ingenuo, EstacionalAjustado, PerfilEstacional]
