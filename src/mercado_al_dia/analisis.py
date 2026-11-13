"""Fase 1 (sin ML): ¿está caro o barato?, ¿cuándo suele subir?, ¿cuánto cuesta la canasta?

Tres piezas, todas deterministas y explicables:

1. **Barato o caro frente a su propio año.** Precio del último mes contra la mediana de los
   12 meses anteriores (``variacion_12m``). La mediana resiste meses atípicos.

2. **Estacionalidad.** Para cada producto se quita la tendencia con una media móvil centrada
   2×12 sobre el logaritmo del precio y se promedia el residuo por mes del calendario. Eso
   da el perfil típico (p. ej. "en marzo suele estar 8 % sobre su tendencia") con su error
   estándar entre años. El consejo "suele subir/bajar el próximo mes" solo se da si el
   cambio esperado supera el umbral y ``z`` errores estándar.

3. **Validación del consejo estacional (principio de honestidad del modelo).** Con origen
   rodante: para cada mes ``t`` desde ``validacion.desde`` se recalcula el perfil usando
   SOLO datos anteriores a ``t`` y se predice la dirección del cambio de ``t`` a ``t+1``.
   Se compara contra la línea base ingenua estacional (repetir la dirección del mismo par
   de meses del año anterior). El consejo se muestra en la página solo si acierta más que
   la línea base y al menos ``aciertos_minimos``. Si no, se dice que no se muestra y por qué.

Todo en pesos corrientes. No es un pronóstico de precio (eso es la fase 2).
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from .sipsa.panel import Precio

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def indice(fecha: dt.date) -> int:
    return fecha.year * 12 + fecha.month - 1


def fecha_de(i: int) -> dt.date:
    return dt.date(i // 12, i % 12 + 1, 1)


Serie = dict[int, float]   # índice de mes -> precio


def series(precios: list[Precio], mercado_id: str) -> dict[str, Serie]:
    s: dict[str, Serie] = defaultdict(dict)
    for p in precios:
        if p.mercado_id == mercado_id:
            s[p.producto_id][indice(p.fecha)] = p.precio
    return dict(s)


# ------------------------------------------------------------------ estacionalidad

def tendencia(serie: Serie) -> dict[int, float]:
    """Media móvil centrada 2×12 del log-precio; solo donde los 13 meses existen."""
    lg = {i: math.log(v) for i, v in serie.items() if v > 0}
    salida = {}
    for i in lg:
        ventana = [lg.get(i + k) for k in range(-6, 7)]
        if any(v is None for v in ventana):
            continue
        salida[i] = (0.5 * ventana[0] + sum(ventana[1:12]) + 0.5 * ventana[12]) / 12
    return salida


@dataclass
class Perfil:
    efecto: list[float | None]          # 12 valores en log, centrados (media 0)
    error: list[float | None]           # error estándar por mes
    anios: list[int]                    # años observados por mes

    def cambio(self, mes: int) -> tuple[float, float] | None:
        """Cambio esperado (log) del mes ``mes`` (0-11) al siguiente, y su error estándar."""
        sig = (mes + 1) % 12
        a, b = self.efecto[mes], self.efecto[sig]
        if a is None or b is None:
            return None
        ea, eb = self.error[mes] or 0.0, self.error[sig] or 0.0
        return b - a, math.sqrt(ea * ea + eb * eb)


def perfil(serie: Serie, hasta: int | None = None, anios_minimos: int = 5) -> Perfil | None:
    """Perfil estacional con datos estrictamente anteriores a ``hasta`` (índice de mes)."""
    if hasta is not None:
        serie = {i: v for i, v in serie.items() if i < hasta}
    tend = tendencia(serie)
    resid: dict[int, list[float]] = defaultdict(list)
    for i, t in tend.items():
        resid[i % 12].append(math.log(serie[i]) - t)
    if min((len(resid[m]) for m in range(12)), default=0) < anios_minimos:
        return None
    medias = [statistics.fmean(resid[m]) for m in range(12)]
    centro = statistics.fmean(medias)
    efecto = [x - centro for x in medias]
    error = [statistics.stdev(resid[m]) / math.sqrt(len(resid[m])) for m in range(12)]
    return Perfil(efecto, error, [len(resid[m]) for m in range(12)])


def consejo(p: Perfil | None, mes: int, efecto_minimo: float, z: float) -> int:
    """+1 suele subir el próximo mes, −1 suele bajar, 0 sin patrón claro."""
    if p is None:
        return 0
    c = p.cambio(mes)
    if c is None:
        return 0
    d, se = c
    if abs(d) < math.log1p(efecto_minimo) or abs(d) < z * se:
        return 0
    return 1 if d > 0 else -1


@dataclass
class Validacion:
    evaluados: int = 0                 # casos en que el método dio consejo y hay dato real
    aciertos: int = 0
    base_evaluados: int = 0            # mismos casos, con dato para la línea base
    base_aciertos: int = 0
    productos: int = 0
    desde: str = ""
    hasta: str = ""
    por_producto: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def tasa(self) -> float:
        return self.aciertos / self.evaluados if self.evaluados else 0.0

    @property
    def tasa_base(self) -> float:
        return self.base_aciertos / self.base_evaluados if self.base_evaluados else 0.0

    def intervalo(self) -> tuple[float, float]:
        """Intervalo de Wilson al 95 % para la tasa de aciertos."""
        n, k = self.evaluados, self.aciertos
        if not n:
            return 0.0, 0.0
        z = 1.96
        p = k / n
        den = 1 + z * z / n
        c = (p + z * z / (2 * n)) / den
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
        return max(0.0, c - h), min(1.0, c + h)


def validar(todas: dict[str, Serie], desde: int, efecto_minimo: float, z: float, anios_minimos: int) -> Validacion:
    v = Validacion()
    ultimo = max((max(s) for s in todas.values() if s), default=desde)
    v.desde, v.hasta = fecha_de(desde).isoformat()[:7], fecha_de(ultimo - 1).isoformat()[:7]
    for pid, s in todas.items():
        ev = ac = 0
        for t in range(desde, ultimo):
            if t not in s or t + 1 not in s:
                continue
            p = perfil(s, hasta=t + 1, anios_minimos=anios_minimos)   # datos hasta el mes t inclusive
            senal = consejo(p, t % 12, efecto_minimo, z)
            if senal == 0:
                continue
            real = math.log(s[t + 1] / s[t])
            if real == 0:
                continue
            ok = (real > 0) == (senal > 0)
            ev += 1
            ac += ok
            if t - 12 in s and t - 11 in s and s[t - 11] != s[t - 12]:
                base = 1 if s[t - 11] > s[t - 12] else -1
                v.base_evaluados += 1
                v.base_aciertos += (real > 0) == (base > 0)
        if ev:
            v.productos += 1
            v.por_producto[pid] = (ev, ac)
            v.evaluados += ev
            v.aciertos += ac
    return v


# ------------------------------------------------------------------ indicadores

@dataclass
class Indicador:
    producto_id: str
    producto: str
    grupo: str
    unidad: str
    mes: str
    precio: float
    mediana_12m: float | None
    variacion_12m: float | None        # precio / mediana de los 12 meses anteriores − 1
    variacion_anual: float | None      # contra el mismo mes del año anterior
    estado: str                        # barato | caro | normal | sin_referencia
    consejo: int                       # +1 suele subir el próximo mes, −1 suele bajar, 0 sin patrón
    cambio_esperado: float | None      # cambio típico al próximo mes (fracción)
    meses_historia: int
    origen: str                        # archivo#hoja!fila del precio mostrado


def indicadores(todas: dict[str, Serie], precios: list[Precio], mercado_id: str, cfg: dict) -> list[Indicador]:
    sen, est = cfg.get("señales", {}), cfg.get("estacionalidad", {})
    umbral = float(sen.get("umbral_barato_caro", 0.10))
    minimo = int(sen.get("meses_minimos_historia", 36))
    ultimo = max(max(s) for s in todas.values() if s)
    info = {}
    for p in precios:
        if p.mercado_id == mercado_id and indice(p.fecha) == ultimo:
            info[p.producto_id] = p
    salida = []
    for pid, s in sorted(todas.items()):
        if ultimo not in s or len(s) < minimo or pid not in info:
            continue
        p = info[pid]
        previos = [s[i] for i in range(ultimo - 12, ultimo) if i in s]
        med = statistics.median(previos) if len(previos) >= 6 else None
        var = s[ultimo] / med - 1 if med else None
        anual = s[ultimo] / s[ultimo - 12] - 1 if ultimo - 12 in s else None
        estado = ("sin_referencia" if var is None else "barato" if var <= -umbral
                  else "caro" if var >= umbral else "normal")
        pf = perfil(s, anios_minimos=int(est.get("anios_minimos", 5)))
        c = consejo(pf, ultimo % 12, float(est.get("efecto_minimo", 0.03)), float(est.get("z", 2.0)))
        cambio = pf.cambio(ultimo % 12) if pf else None
        salida.append(Indicador(pid, p.producto, p.grupo, p.unidad, fecha_de(ultimo).isoformat()[:7], s[ultimo], med,
                                var, anual, estado, c, math.expm1(cambio[0]) if cambio else None, len(s),
                                f"{p.archivo}#{p.hoja}!{p.fila}"))
    return salida


# ------------------------------------------------------------------ canasta

@dataclass
class Canasta:
    nombre: str
    componentes: list[dict]            # producto, producto_id, cantidad, unidad
    costo: dict[int, float]            # solo meses con todos los productos
    faltantes: dict[str, list[str]]    # producto -> meses sin dato (en los últimos 24)
    no_encontrados: list[str]


def canasta(todas: dict[str, Serie], precios: list[Precio], mercado_id: str, cfg: dict, catalogo) -> Canasta:
    comps, no = [], []
    unidades = {p.producto_id: p.unidad for p in precios}
    for c in cfg.get("productos", []):
        pid, nombre = catalogo.producto(c["producto"])
        if pid not in todas:
            no.append(c["producto"])
            continue
        comps.append({"producto": nombre, "producto_id": pid, "cantidad": float(c["cantidad"]),
                      "unidad": unidades.get(pid, "kg")})
    meses = sorted(set().union(*(todas[c["producto_id"]].keys() for c in comps))) if comps else []
    costo, faltan = {}, defaultdict(list)
    recientes = set(meses[-24:])
    for i in meses:
        if all(i in todas[c["producto_id"]] for c in comps):
            costo[i] = sum(todas[c["producto_id"]][i] * c["cantidad"] for c in comps)
        elif i in recientes:
            for c in comps:
                if i not in todas[c["producto_id"]]:
                    faltan[c["producto"]].append(fecha_de(i).isoformat()[:7])
    return Canasta(cfg.get("nombre", "Canasta"), comps, costo, dict(faltan), no)
