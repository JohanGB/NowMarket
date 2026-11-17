"""Del registro crudo al panel limpio: normalización, unidades, equivalencias y calidad.

Reglas (todas configurables en ``config/productos.yaml``):
- Mercados y productos se identifican por su nombre "plano" (sin tildes, minúsculas,
  sin signos), así "Frigorífico Ble Ltda." y "Frigorífico Ble Ltda," son el mismo.
  Se muestra el nombre más frecuente en los datos.
- Productos renombrados por el DANE se unen solo si están en ``equivalencias``.
- Cada producto lleva su unidad ($/kg, $/unidad o $/litro) según la nota al pie del DANE.
- Duplicados (mismo mes, mercado y producto): si el precio es igual se deja uno; si es
  distinto no se elige ninguno al azar: se descartan ambos y se reporta.
- Saltos extremos de un mes a otro (×3 o ÷3) se reportan pero no se corrigen.
- Saltos ×3 entre observaciones separadas por un hueco (`saltos_con_hueco`) y datos aislados que difieren
  ×10 de su dato anterior y de su siguiente en sentidos opuestos (`datos_sospechosos`): solo se reportan;
  el panel no cambia (hallazgo 7 de la auditoría independiente).
"""
from __future__ import annotations

import collections
import datetime as dt
import re
from dataclasses import dataclass, field

from .lector import Registro, plano

SALTO_EXTREMO = 3.0
SALTO_SOSPECHOSO = 10.0     # dato aislado: ×10 frente al anterior y al siguiente, en sentidos opuestos


@dataclass
class Precio:
    fecha: dt.date
    grupo: str
    producto_id: str
    producto: str
    unidad: str
    mercado_id: str
    mercado: str
    precio: float
    producto_original: str
    archivo: str
    hoja: str
    fila: int
    sha256: str


@dataclass
class Calidad:
    registros_leidos: int = 0
    registros_por_archivo: dict[str, int] = field(default_factory=dict)
    duplicados_identicos: int = 0
    duplicados_en_conflicto: list[dict] = field(default_factory=list)
    equivalencias_aplicadas: dict[str, int] = field(default_factory=dict)
    saltos_extremos: list[dict] = field(default_factory=list)
    saltos_con_hueco: list[dict] = field(default_factory=list)
    datos_sospechosos: list[dict] = field(default_factory=list)
    incidencias: list[dict] = field(default_factory=list)


class Catalogo:
    def __init__(self, cfg: dict):
        self.unidad_defecto = cfg.get("unidad_por_defecto", "kg")
        self.unidades = [(re.compile(u["patron"]), u["unidad"]) for u in cfg.get("unidades", [])]
        self.equivalencias = {plano(e["desde"]): e["hacia"] for e in cfg.get("equivalencias", [])}
        m = cfg.get("mercados", {})
        self.referencia = plano(m.get("referencia", "Bogotá, D.C., Corabastos"))
        self.rotulo_referencia = m.get("rotulo_referencia", m.get("referencia", ""))
        self.comparacion = [plano(x) for x in m.get("comparacion", [])]
        self.prefijos = [plano(x) for x in m.get("guardar_prefijos", [])]

    def producto(self, nombre: str) -> tuple[str, str]:
        """(identificador, nombre a mostrar) después de aplicar equivalencias."""
        p = plano(nombre)
        if p in self.equivalencias:
            destino = self.equivalencias[p]
            return plano(destino), destino
        return p, nombre

    def unidad(self, producto_id: str) -> str:
        for patron, unidad in self.unidades:
            if patron.search(producto_id):
                return unidad
        return self.unidad_defecto

    def guardar(self, mercado_id: str) -> bool:
        return not self.prefijos or any(mercado_id.startswith(p) for p in self.prefijos)


def construir(registros, catalogo: Catalogo, incidencias=None) -> tuple[list[Precio], Calidad]:
    cal = Calidad()
    por_archivo: collections.Counter = collections.Counter()
    nombres_mercado: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    nombres_producto: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    grupos: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    candidatos: dict[tuple, list[Registro]] = collections.defaultdict(list)
    grupos_planos: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    for r in registros:
        cal.registros_leidos += 1
        grupos_planos[plano(r.grupo)][r.grupo] += 1
        por_archivo[r.archivo] += 1
        m_id = plano(r.mercado)
        nombres_mercado[m_id][r.mercado] += 1
        if not catalogo.guardar(m_id):
            continue
        p_id, p_nombre = catalogo.producto(r.producto)
        if p_id != plano(r.producto):
            cal.equivalencias_aplicadas[r.producto] = cal.equivalencias_aplicadas.get(r.producto, 0) + 1
        nombres_producto[p_id][p_nombre] += 1
        grupos[p_id][plano(r.grupo)] += 1
        candidatos[(r.fecha, m_id, p_id)].append(r)

    cal.registros_por_archivo = dict(sorted(por_archivo.items()))
    mercado_nombre = {k: v.most_common(1)[0][0] for k, v in nombres_mercado.items()}
    producto_nombre = {k: v.most_common(1)[0][0] for k, v in nombres_producto.items()}
    nombre_grupo = {g: _con_tildes(v) for g, v in grupos_planos.items()}
    grupo_nombre = {k: nombre_grupo[v.most_common(1)[0][0]] for k, v in grupos.items()}

    precios: list[Precio] = []
    for (fecha, m_id, p_id), rs in sorted(candidatos.items()):
        if len(rs) > 1:
            valores = {r.precio for r in rs}
            if len(valores) > 1:
                cal.duplicados_en_conflicto.append({
                    "fecha": fecha.isoformat(), "mercado": mercado_nombre[m_id], "producto": producto_nombre[p_id],
                    "precios": sorted(valores), "origenes": [f"{r.archivo}#{r.hoja}!{r.fila}" for r in rs]})
                continue
            cal.duplicados_identicos += len(rs) - 1
        r = rs[0]
        precios.append(Precio(fecha, grupo_nombre[p_id], p_id, producto_nombre[p_id], catalogo.unidad(p_id),
                              m_id, mercado_nombre[m_id], r.precio, r.producto, r.archivo, r.hoja, r.fila, r.sha256))

    # Saltos extremos entre meses consecutivos de una misma serie (se reportan, no se tocan).
    previo: dict[tuple, Precio] = {}
    for p in precios:  # ya vienen ordenados por fecha
        clave = (p.mercado_id, p.producto_id)
        q = previo.get(clave)
        if q and _meses(q.fecha, p.fecha) == 1:
            razon = p.precio / q.precio
            if razon >= SALTO_EXTREMO or razon <= 1 / SALTO_EXTREMO:
                cal.saltos_extremos.append({"mercado": p.mercado, "producto": p.producto, "desde": q.fecha.isoformat(),
                                            "hasta": p.fecha.isoformat(), "precio_antes": q.precio,
                                            "precio_despues": p.precio, "origen": f"{p.archivo}#{p.hoja}!{p.fila}"})
        previo[clave] = p
    _reportar_huecos_y_sospechosos(precios, cal)
    if incidencias:
        cal.incidencias = [vars(i) for i in incidencias]
    return precios, cal


def _reportar_huecos_y_sospechosos(precios: list[Precio], cal: Calidad) -> None:
    """Solo reporta; no modifica ni borra ningún precio. ``precios`` viene ordenado por fecha."""
    series: dict[tuple, list[Precio]] = collections.defaultdict(list)
    for p in precios:
        series[(p.mercado_id, p.producto_id)].append(p)
    for lista in series.values():
        for q, p in zip(lista, lista[1:]):
            hueco = _meses(q.fecha, p.fecha) - 1
            razon = p.precio / q.precio
            if hueco > 0 and (razon >= SALTO_EXTREMO or razon <= 1 / SALTO_EXTREMO):
                cal.saltos_con_hueco.append({
                    "mercado": p.mercado, "producto": p.producto, "desde": q.fecha.isoformat(), "hasta": p.fecha.isoformat(),
                    "meses_de_hueco": hueco, "precio_antes": q.precio, "precio_despues": p.precio,
                    "origen": f"{p.archivo}#{p.hoja}!{p.fila}"})
        for a, b, c in zip(lista, lista[1:], lista[2:]):
            antes, despues = b.precio / a.precio, c.precio / b.precio
            if (antes <= 1 / SALTO_SOSPECHOSO and despues >= SALTO_SOSPECHOSO) or                (antes >= SALTO_SOSPECHOSO and despues <= 1 / SALTO_SOSPECHOSO):
                cal.datos_sospechosos.append({
                    "mercado": b.mercado, "producto": b.producto, "fecha": b.fecha.isoformat(), "precio": b.precio,
                    "precio_anterior": a.precio, "precio_siguiente": c.precio,
                    "razon_anterior": antes, "razon_siguiente": despues,
                    "origen": f"{b.archivo}#{b.hoja}!{b.fila}",
                    "motivo": f"el precio difiere ×{max(antes, 1 / antes):.0f} del dato anterior y ×{max(despues, 1 / despues):.0f} "
                              "del siguiente, en sentidos opuestos; posible error de la fuente o de unidad. Se conserva sin cambios."})


def _con_tildes(variantes: collections.Counter) -> str:
    """Entre variantes del mismo nombre ("LACTEOS" / "LÁCTEOS"), prefiere la que tiene tildes."""
    return max(variantes, key=lambda x: (sum(1 for c in x if ord(c) > 127), variantes[x]))


def _meses(a: dt.date, b: dt.date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month
