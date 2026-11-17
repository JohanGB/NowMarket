"""Datos de modelado: matriz de log-precios de Corabastos y variables exógenas sin fuga.

Las exógenas se alinean al mes en que realmente se conocen:
- ONI (NOAA): anomalía de la temporada trimestral; se asigna al mes central.
- Abastecimiento (SIPSA_A, DANE): toneladas mensuales que ingresan a Corabastos.
Los rezagos de config/modelos.yaml garantizan que en el origen t solo se use lo publicado.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

TEMPORADAS = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8,
              "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}


@dataclass
class Datos:
    logp: pd.DataFrame            # índice: Period[M]; columnas: producto_id
    nombres: dict[str, str]
    grupos: dict[str, str]
    unidades: dict[str, str]
    oni: pd.Series                # anomalía ONI por mes central (Period[M])
    abastecimiento: pd.Series     # log toneladas Corabastos por mes (Period[M])
    evaluacion: list[str]         # productos que se reportan
    entrenamiento: list[str]      # candidatos para modelos globales; la lista real se elige en cada
                                  # origen con productos_entrenamiento() (solo datos hasta el origen)

    @property
    def ultimo(self) -> pd.Period:
        return self.logp.index.max()


def productos_entrenamiento(logp: pd.DataFrame, hasta: pd.Period, minimo: int,
                            candidatos: list[str] | None = None) -> list[str]:
    """Productos con al menos ``min(minimo, meses transcurridos)`` meses con precio hasta ``hasta``.

    Corrección (a) de la auditoría (17-nov-2026): antes se contaban los meses de toda la muestra, lo que
    usaba datos posteriores al origen. Contados solo hasta el origen, ningún producto llega a 120 meses
    antes de 2022-12; por eso el mínimo se topa en los meses transcurridos desde el inicio del panel
    (decisión del autor, D-030): en los orígenes tempranos se exige la historia completa.
    """
    hist = logp.loc[:hasta]
    exigidos = min(int(minimo), len(hist))
    cols = hist.columns if candidatos is None else [c for c in hist.columns if c in set(candidatos)]
    return [p for p in cols if hist[p].notna().sum() >= exigidos]


def leer_oni(ruta: Path) -> pd.Series:
    filas = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines()[1:]:
        partes = linea.split()
        if len(partes) == 4 and partes[0] in TEMPORADAS:
            filas[pd.Period(year=int(partes[1]), month=TEMPORADAS[partes[0]], freq="M")] = float(partes[3])
    return pd.Series(filas, name="oni").sort_index()


def leer_abastecimiento(ruta: Path, mercado: str = "Bogotá, D.C., Corabastos") -> pd.Series:
    import openpyxl

    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = next(w for w in wb.worksheets if "mensual" in w.title.lower())
        col, filas = None, {}
        for fila in ws.iter_rows(values_only=True):
            if col is None:
                if fila and fila[0] == "Fecha":
                    col = next(i for i, x in enumerate(fila) if x and str(x).strip() == mercado)
                continue
            f, v = fila[0], fila[col] if col < len(fila) else None
            if hasattr(f, "year") and isinstance(v, (int, float)) and v > 0:
                filas[pd.Period(year=f.year, month=f.month, freq="M")] = float(np.log(v))
    finally:
        wb.close()
    return pd.Series(filas, name="abastecimiento").sort_index()


def cargar(raiz: Path, cfg: dict) -> Datos:
    raiz = Path(raiz)
    ruta = raiz / "data" / "procesado" / "precios_bogota.csv"
    if not ruta.exists():
        raise FileNotFoundError("Falta data/procesado/precios_bogota.csv: ejecute primero `python -m mercado_al_dia`.")
    cat = yaml.safe_load((raiz / "config" / "productos.yaml").read_text(encoding="utf-8"))
    from ..sipsa.lector import plano
    referencia = plano(cat["mercados"]["referencia"])
    registros, nombres, grupos, unidades = [], {}, {}, {}
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if plano(r["mercado"]) != referencia:
                continue
            registros.append((pd.Period(r["fecha"], freq="M"), r["producto_id"], float(r["precio"])))
            nombres[r["producto_id"]], grupos[r["producto_id"]], unidades[r["producto_id"]] = r["producto"], r["grupo"], r["unidad"]
    df = pd.DataFrame(registros, columns=["mes", "pid", "precio"])
    logp = np.log(df.pivot(index="mes", columns="pid", values="precio"))
    logp = logp.reindex(pd.period_range(logp.index.min(), logp.index.max(), freq="M")).sort_index(axis=1)

    if cfg.get("productos_evaluacion") == "canasta":
        can = yaml.safe_load((raiz / "config" / "canasta.yaml").read_text(encoding="utf-8"))
        evaluacion = [plano(p["producto"]) for p in can["productos"]]
    else:
        evaluacion = [plano(p) for p in cfg["productos_evaluacion"]]
    faltan = [p for p in evaluacion if p not in logp.columns]
    if faltan:
        raise ValueError(f"Productos de evaluación sin datos: {faltan}")
    entrenamiento = list(logp.columns)     # candidatos: cada modelo global filtra hasta su origen

    exo = raiz / "data" / "raw"
    oni = leer_oni(exo / "exogenas" / "noaa_oni.ascii.txt")
    abast = leer_abastecimiento(exo / "sipsa" / "abastecimiento" / "sipsa_a_series_historicas_2013_2026.xlsx")
    return Datos(logp, nombres, grupos, unidades, oni, abast, evaluacion, entrenamiento)
