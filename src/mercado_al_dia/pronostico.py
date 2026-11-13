"""Pronóstico de producción: el modelo seleccionado en validación, entrenado con todos los datos.

Lee ``models/registro/seleccion.json`` (qué familia gana en cada horizonte y su calibración
conformal) y pronostica desde el último mes disponible. Si la selección no existe o se hizo con
otra configuración u otros datos, no pronostica (el tablero lo dice) en vez de usar un modelo
sin validar.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .modelos import evaluacion as ev
from .modelos import familias
from .modelos.datos import Datos, cargar


@dataclass
class Pronostico:
    origen: str
    filas: list[dict]               # pid, h, mes, q10, q50, q90 (en pesos), modelo
    seleccion: dict[int, str]
    prueba: dict | None             # métricas de la prueba única, para mostrarlas
    motivo_ausente: str = ""


def _familia(nombre: str, cfg: dict):
    clases = {c.nombre: c for c in familias.LINEAS_BASE} | {"sarimax": familias.Sarimax, "lightgbm": familias.LightGBMGlobal}
    if nombre == "nbeats":
        from .modelos.nbeats import NBeats
        return NBeats(cfg)
    return clases[nombre](cfg)


def pronosticar(raiz: Path, datos: Datos | None = None) -> Pronostico:
    raiz = Path(raiz)
    cfg = yaml.safe_load((raiz / "config" / "modelos.yaml").read_text(encoding="utf-8"))
    ruta = raiz / "models" / "registro" / "seleccion.json"
    if not ruta.exists():
        return Pronostico("", [], {}, None, "aún no se ha corrido la validación de modelos")
    sel = json.loads(ruta.read_text(encoding="utf-8"))
    h = ev.huella(raiz, cfg)
    if sel["huella"]["sha256_config"] != h["sha256_config"]:
        return Pronostico("", [], {}, None, "la configuración cambió desde la validación: repítala")
    if sel["huella"]["sha256_datos"] != h["sha256_datos"]:
        return Pronostico("", [], {}, None, "los datos crudos cambiaron desde la validación: repítala con los datos nuevos")
    datos = datos or cargar(raiz, cfg)
    origen = datos.ultimo
    eleccion = {int(k): v["modelo"] for k, v in sel["seleccion"].items()}
    filas = []
    for nombre in sorted(set(eleccion.values())):
        m = _familia(nombre, cfg)
        m.ajustar(datos, origen)                       # todos los objetivos observados
        cqr = {int(k): v for k, v in sel["cqr"][nombre].items()}
        for f in m.predecir(datos, origen, datos.evaluacion):
            if eleccion.get(f["h"]) != nombre:
                continue
            a = cqr.get(f["h"], 0.0)
            filas.append({"pid": f["pid"], "h": f["h"], "mes": str(origen + f["h"]), "modelo": nombre,
                          "q10": float(np.exp(f["q10"] - a)), "q50": float(np.exp(f["q50"])),
                          "q90": float(np.exp(f["q90"] + a)), "actual": float(np.exp(datos.logp.at[origen, f["pid"]]))})
    prueba = None
    rp = raiz / "models" / "registro" / "prueba.json"
    if rp.exists():
        prueba = json.loads(rp.read_text(encoding="utf-8"))
    return Pronostico(str(origen), filas, eleccion, prueba)


def alertas(p: Pronostico, nombres: dict[str, str], cfg_alertas: dict) -> list[dict]:
    """Alertas para tenderos con el pronóstico a 1 mes: alza o baja probable."""
    umbral = float(cfg_alertas.get("cambio_minimo", 0.05))
    salida = []
    for f in p.filas:
        if f["h"] != 1:
            continue
        cambio = f["q50"] / f["actual"] - 1
        if f["q10"] > f["actual"]:
            nivel, texto = "alza_segura", "subirá con al menos 90 % de probabilidad"
        elif f["q90"] < f["actual"]:
            nivel, texto = "baja_segura", "bajará con al menos 90 % de probabilidad"
        elif cambio >= umbral:
            nivel, texto = "alza_probable", f"lo más probable es que suba ({cambio:+.0%})"
        elif cambio <= -umbral:
            nivel, texto = "baja_probable", f"lo más probable es que baje ({cambio:+.0%})"
        else:
            continue
        salida.append({"pid": f["pid"], "producto": nombres.get(f["pid"], f["pid"]), "nivel": nivel,
                       "texto": texto, "cambio": cambio, "mes": f["mes"]})
    orden = {"alza_segura": 0, "baja_segura": 1, "alza_probable": 2, "baja_probable": 3}
    return sorted(salida, key=lambda a: (orden[a["nivel"]], -abs(a["cambio"])))


def tabla(p: Pronostico) -> pd.DataFrame:
    return pd.DataFrame(p.filas)
