"""Lector unificado de las series históricas mensuales de precios mayoristas SIPSA (DANE).

El DANE cambió el formato de estos Excel varias veces (confirmado leyendo los archivos):

| Archivo        | Hojas de datos                 | Columna del mercado | Columna del precio                  |
|----------------|--------------------------------|---------------------|-------------------------------------|
| 2013–2017      | una por año (1.1 … 1.5)        | Fuente              | Precio                              |
| 2018           | una (2018)                     | Fuente              | Precio                              |
| 2019           | una por mes (Ene 19 …)         | Fuente              | Precio  por kilogramo*              |
| 2020           | una por mes                    | Mercado             | Precio  por kilogramo*              |
| 2021–2023      | una por mes                    | Mercado             | Precio promedio por kilogramo*      |
| 2024           | una (2024)                     | Mercado             | Precio promedio por kilogramo*      |
| 2025           | una (2025) + CPC               | Mercado             | ídem, con Código CPC                |
| 2026           | una (2026) + Fuentes + CPC     | Mercado             | ídem, con códigos DIVIPOLA          |

Por eso el lector no usa posiciones fijas: en cada hoja busca la fila de encabezado por
nombre (``Fecha`` y ``Producto``) y ubica las columnas por sinónimos. Cada registro
conserva archivo, hoja y fila de origen, más el SHA-256 del archivo, para que cualquier
precio pueda rastrearse hasta la celda de donde salió. Los archivos nunca se modifican.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

FILAS_BUSQUEDA_ENCABEZADO = 30

# Sinónimos de columna (en forma "plana": minúsculas, sin tildes ni signos).
SINONIMOS = {
    "fecha": ("fecha",),
    "grupo": ("grupo",),
    "producto": ("producto",),
    "mercado": ("mercado", "fuente"),
    "precio": ("precio", "precio por kilogramo", "precio promedio por kilogramo"),
    "cpc": ("codigo cpc",),
}

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
         "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}


class FormatoDesconocido(ValueError):
    """Una hoja parece tener datos pero no se reconocen sus columnas."""


def plano(texto: object) -> str:
    """Minúsculas, sin tildes, sin signos y con espacios simples."""
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


@dataclass(frozen=True)
class Registro:
    fecha: dt.date            # primer día del mes
    grupo: str
    producto: str
    mercado: str
    precio: float             # pesos corrientes por kilogramo
    cpc: str
    archivo: str              # ruta relativa a data/raw
    hoja: str
    fila: int                 # fila de Excel (1 = primera)
    sha256: str


@dataclass
class Incidencia:
    archivo: str
    hoja: str
    fila: int
    motivo: str
    valor: str = ""


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _columnas(encabezado: tuple) -> dict[str, int] | None:
    nombres = [plano(x) for x in encabezado]
    if "fecha" not in nombres or "producto" not in nombres:
        return None
    cols: dict[str, int] = {}
    for clave, sinonimos in SINONIMOS.items():
        for i, n in enumerate(nombres):
            if n in sinonimos or (clave == "precio" and n.startswith("precio")):
                cols[clave] = i
                break
    faltan = {"fecha", "producto", "mercado", "precio"} - set(cols)
    if faltan:
        raise FormatoDesconocido(f"faltan columnas {sorted(faltan)} en el encabezado {encabezado!r}")
    return cols


def _fecha(valor: object) -> dt.date | None:
    if isinstance(valor, dt.datetime):
        return valor.date().replace(day=1)
    if isinstance(valor, dt.date):
        return valor.replace(day=1)
    t = plano(valor)
    if m := re.fullmatch(r"(\d{4}) (\d{1,2})(?: \d{1,2})?(?: 0+ 0+ 0+)?", t):
        return dt.date(int(m[1]), int(m[2]), 1)
    if m := re.fullmatch(r"([a-z]{3})[a-z]* (?:de )?(\d{4})", t):
        if m[1] in MESES:
            return dt.date(int(m[2]), MESES[m[1]], 1)
    return None


def _precio(valor: object) -> float | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    t = str(valor).strip().replace("$", "").replace(" ", "")
    if not t or t in {"-", "n.d.", "nd", "ND"}:
        return None
    # Formato colombiano en texto: 1.234,5 o 3.500 (punto de miles).
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    elif "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def leer_archivo(ruta: Path, raiz: Path, incidencias: list[Incidencia] | None = None) -> Iterator[Registro]:
    """Recorre todas las hojas con datos de un Excel SIPSA y produce un registro por fila."""
    import openpyxl  # importación tardía: solo se necesita al leer los Excel

    incidencias = incidencias if incidencias is not None else []
    rel = ruta.relative_to(raiz).as_posix()
    huella = sha256_archivo(ruta)
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            cols = None
            for n_fila, fila in enumerate(ws.iter_rows(values_only=True), start=1):
                if cols is None:
                    if n_fila > FILAS_BUSQUEDA_ENCABEZADO:
                        break      # hoja sin datos (índice, ficha, CPC, fuentes)
                    cols = _columnas(fila)
                    continue
                if not fila or all(v is None for v in fila):
                    continue
                valor_fecha = fila[cols["fecha"]] if cols["fecha"] < len(fila) else None
                producto = fila[cols["producto"]] if cols["producto"] < len(fila) else None
                if valor_fecha is None and producto is None:
                    continue
                fecha = _fecha(valor_fecha)
                if fecha is None:
                    # Notas al pie ("* Precio promedio...", "Fuente: DANE") no son datos.
                    if producto is None and isinstance(valor_fecha, str):
                        continue
                    incidencias.append(Incidencia(rel, ws.title, n_fila, "fecha ilegible", str(valor_fecha)))
                    continue
                precio = _precio(fila[cols["precio"]] if cols["precio"] < len(fila) else None)
                mercado = fila[cols["mercado"]] if cols["mercado"] < len(fila) else None
                if not producto or not mercado:
                    incidencias.append(Incidencia(rel, ws.title, n_fila, "sin producto o mercado"))
                    continue
                if precio is None or precio <= 0:
                    incidencias.append(Incidencia(rel, ws.title, n_fila, "precio vacío o no positivo",
                                                  str(fila[cols["precio"]] if cols["precio"] < len(fila) else "")))
                    continue
                cpc = fila[cols["cpc"]] if "cpc" in cols and cols["cpc"] < len(fila) else ""
                yield Registro(
                    fecha=fecha,
                    grupo=" ".join(str(fila[cols["grupo"]] or "").split()).upper() if "grupo" in cols else "",
                    producto=" ".join(str(producto).split()),
                    mercado=" ".join(str(mercado).split()),
                    precio=precio,
                    cpc=str(cpc or "").strip(),
                    archivo=rel, hoja=ws.title, fila=n_fila, sha256=huella,
                )
    finally:
        wb.close()


def leer_carpeta(carpeta: Path, raiz: Path, incidencias: list[Incidencia] | None = None) -> Iterator[Registro]:
    for ruta in sorted(Path(carpeta).glob("*.xlsx")):
        if ruta.name.startswith("~$"):        # archivo temporal de Excel abierto
            continue
        yield from leer_archivo(ruta, raiz, incidencias)
