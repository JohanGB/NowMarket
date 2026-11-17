"""Pruebas de los hallazgos de la auditoría independiente (docs/auditoria_independiente.md, 17-nov-2026).

Escritas ANTES de corregir (paso 1). Dos tipos:
- Hallazgos 1, 2, 3 y 5: fallaban con el código de la etiqueta ``estado-auditado``.
- Errores que las pruebas no detectaban (mutantes M5–M8 de la auditoría): pasan con el código correcto
  y fallan si alguien introduce ese error.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import math

import numpy as np
import pandas as pd
import pytest

from mercado_al_dia.modelos import evaluacion as ev
from mercado_al_dia.modelos import familias, metricas
from mercado_al_dia.sipsa import panel

from test_fase1 import _catalogo, _reg
from test_fase2 import CFG, _cfg_rapida, _datos, _pred, _proyecto

CUANTILES = [0.1, 0.5, 0.9]


# ------------------------------------------------------------------ hallazgo 3: lista de entrenamiento

def _datos_con_producto_nuevo():
    """Datos sintéticos más un producto que empieza en 2016-01: su historia completa supera el mínimo
    de entrenamiento, pero la que existía en el origen 2020-06 no."""
    d = _datos(meses=120)
    s = d.logp["p0"].copy() + 0.5
    s.loc[: pd.Period("2015-12", "M")] = np.nan
    d.logp["nuevo"] = s
    d.nombres["nuevo"], d.grupos["nuevo"], d.unidades["nuevo"] = "NUEVO", "G", "kg"
    return d


def _como_se_veia_en(d, origen, cfg):
    """Lo que `cargar` habría producido con los datos publicados hasta el origen."""
    d2 = copy.deepcopy(d)
    d2.logp = d.logp.loc[:origen].copy()
    minimo = int(cfg["meses_minimos_entrenamiento"])
    d2.entrenamiento = [p for p in d2.logp.columns if d2.logp[p].notna().sum() >= minimo]
    return d2


GLOBALES = [familias.LightGBMGlobal,
            pytest.param("nbeats", marks=pytest.mark.filterwarnings("ignore"))]


@pytest.mark.parametrize("clase", GLOBALES)
def test_lista_de_entrenamiento_solo_con_datos_hasta_el_origen(clase):
    """Hallazgo 3: el pronóstico en t no puede depender de cuántos meses tendrá cada producto después de t."""
    if clase == "nbeats":
        pytest.importorskip("jax")
        from mercado_al_dia.modelos.nbeats import NBeats as clase
    cfg = _cfg_rapida()                                  # meses_minimos_entrenamiento = 60
    d = _datos_con_producto_nuevo()
    d.entrenamiento = [p for p in d.logp.columns if d.logp[p].notna().sum() >= cfg["meses_minimos_entrenamiento"]]
    origen = pd.Period("2020-06", "M")
    assert "nuevo" in d.entrenamiento                    # con la muestra completa tiene 72 meses
    d2 = _como_se_veia_en(d, origen, cfg)
    assert "nuevo" not in d2.entrenamiento               # en el origen tenía 54

    a, b = clase(cfg), clase(cfg)
    a.ajustar(d, origen)
    b.ajustar(d2, origen)
    pa = pd.DataFrame(a.predecir(d, origen, d.evaluacion)).set_index(["pid", "h"]).sort_index()
    pb = pd.DataFrame(b.predecir(d2, origen, d.evaluacion)).set_index(["pid", "h"]).sort_index()
    assert len(pa) == len(d.evaluacion) * 3
    pd.testing.assert_frame_equal(pa, pb)


# ------------------------------------------------------------------ M5: SARIMAX (y N-BEATS) sin futuro

@pytest.mark.parametrize("nombre", ["sarimax", "nbeats"])
def test_sarimax_y_nbeats_no_miran_el_futuro(nombre):
    """M5: estimar SARIMAX (o N-BEATS) con meses posteriores al origen debe notarse."""
    if nombre == "nbeats":
        pytest.importorskip("jax")
        from mercado_al_dia.modelos.nbeats import NBeats as clase
    else:
        clase = familias.Sarimax
    cfg = _cfg_rapida()
    d = _datos(meses=120)
    origen = pd.Period("2020-06", "M")
    a = clase(cfg)
    a.ajustar(d, origen)
    pa = pd.DataFrame(a.predecir(d, origen, d.evaluacion)).set_index(["pid", "h"]).sort_index()
    d2 = copy.deepcopy(d)
    d2.logp.loc[origen + 1:] += 3.0
    d2.oni.loc[origen - 1:] += 5.0                        # ONI centrado en t−1 o después: aún no publicado en t−5
    b = clase(cfg)
    b.ajustar(d2, origen)
    pb = pd.DataFrame(b.predecir(d2, origen, d2.evaluacion)).set_index(["pid", "h"]).sort_index()
    assert len(pa) == len(d.evaluacion) * 3
    pd.testing.assert_frame_equal(pa, pb)


# ------------------------------------------------------------------ hallazgo 5: orden estadístico de CQR

def test_cqr_usa_el_orden_estadistico_de_romano():
    """Hallazgo 5: el ajuste es el elemento ⌈(n+1)·cobertura⌉ de los errores ordenados, no el siguiente."""
    e = np.arange(1.0, 10.0)                              # n = 9 → k = ⌈10·0,8⌉ = 8 → ajuste 8
    p = pd.DataFrame({"h": 1, "y": e, "q10": 0.0, "q50": 0.0, "q90": 0.0})
    assert ev.cqr(p, 0.8)[1] == 8.0
    e = np.arange(1.0, 101.0)                             # n = 100 → k = ⌈101·0,8⌉ = 81
    p = pd.DataFrame({"h": 1, "y": e, "q10": 0.0, "q50": 0.0, "q90": 0.0})
    assert ev.cqr(p, 0.8)[1] == 81.0


# ------------------------------------------------------------------ M6: calibración solo con la validación

def test_la_prueba_no_recalibra_con_sus_propios_datos(tmp_path, monkeypatch):
    """M6: la fase de prueba aplica el CQR de la validación; nunca lo calcula con datos de la prueba."""
    from mercado_al_dia.modelos import experimento

    raiz = _proyecto(tmp_path, _cfg_rapida())
    experimento.correr(raiz, "validacion", con_nbeats=False, decir=lambda *_: None)

    def prohibido(*_a, **_k):
        raise AssertionError("cqr() llamado durante la prueba: calibraría con datos de la prueba")

    monkeypatch.setattr(ev, "cqr", prohibido)
    experimento.correr(raiz, "prueba", con_nbeats=False, decir=lambda *_: None)
    sel = json.loads((raiz / "models" / "registro" / "seleccion.json").read_text(encoding="utf-8"))
    prueba = pd.read_csv(raiz / "models" / "registro" / "pronosticos_prueba.csv", encoding="utf-8-sig")
    assert set(prueba["modelo"]) <= set(sel["cqr"])


# ------------------------------------------------------------------ M8: la validación no toca la prueba

def test_validacion_solo_con_objetivos_dentro_de_la_validacion(tmp_path):
    """M8: ningún objetivo de la validación cae en la ventana de prueba."""
    from mercado_al_dia.modelos import experimento

    cfg = _cfg_rapida()
    raiz = _proyecto(tmp_path, cfg)
    experimento.correr(raiz, "validacion", con_nbeats=False, decir=lambda *_: None)
    v = pd.read_csv(raiz / "models" / "registro" / "pronosticos_validacion.csv", encoding="utf-8-sig")
    hasta = pd.Period(cfg["validacion"]["hasta"], "M")
    assert len(v) and max(pd.Period(o, "M") for o in v["objetivo"]) <= hasta
    assert min(pd.Period(o, "M") for o in v["origen"]) >= pd.Period(cfg["validacion"]["desde"], "M")


# ------------------------------------------------------------------ M7 y hallazgo 2: bootstrap de orígenes

def _repetir_productos(p: pd.DataFrame, veces: int) -> pd.DataFrame:
    return pd.concat([p.assign(pid=p["pid"] + f"_{k}") for k in range(veces)], ignore_index=True)


@pytest.mark.parametrize("bloque", [1, 3])
def test_bootstrap_remuestrea_origenes_completos_no_casos(bloque):
    """M7: copiar cada producto tres veces no agrega información (los casos de un origen comparten el
    choque); con orígenes completos el IC es idéntico, con casos sueltos se estrecharía."""
    bueno, malo = _pred("m", 0.6), _pred("b", 1.0)
    r1 = metricas.bootstrap_mejora(bueno, malo, CUANTILES, 500, 7, bloque=bloque)
    r3 = metricas.bootstrap_mejora(_repetir_productos(bueno, 3), _repetir_productos(malo, 3), CUANTILES, 500, 7, bloque=bloque)
    assert r3 == pytest.approx(r1, abs=1e-12)


def test_bloques_circulares_dan_el_mismo_peso_a_todos_los_origenes():
    """Hallazgo 2: con bloques móviles no circulares los primeros y últimos orígenes salen menos."""
    n, b, reps = 23, 6, 20000
    idx = metricas.indices_bloques(n, b, reps, np.random.default_rng(1))
    assert idx.shape == (reps, n)
    frecuencia = np.bincount(idx.ravel(), minlength=n) / idx.size
    np.testing.assert_allclose(frecuencia, 1 / n, rtol=0.05)


def test_bloques_circulares_son_consecutivos_y_dan_la_vuelta():
    idx = metricas.indices_bloques(10, 4, 200, np.random.default_rng(2))
    for fila in idx:
        for k in range(0, 8, 4):                            # bloques completos dentro de la fila
            assert all((fila[k + j + 1] - fila[k + j]) % 10 == 1 for j in range(3))


# ------------------------------------------------------------------ hallazgo 1: regla de despliegue

def test_la_configuracion_fija_el_bloque_y_cumple_al_menos_h():
    """Hallazgo 1: docs/modelos.md promete `bootstrap_bloque` ≥ h en config/modelos.yaml."""
    assert "bootstrap_bloque" in CFG
    assert int(CFG["bootstrap_bloque"]) >= max(CFG["horizontes"])


def test_seleccion_usa_el_bloque_de_la_configuracion_y_no_un_valor_por_defecto():
    base = _pred("ingenuo", 1.0, semilla=5)
    otro = _pred("lightgbm", 0.5, semilla=5)
    pred = pd.concat([base, otro])
    tabla = ev.tabla_metricas(pred, {"cuantiles": CUANTILES}, {"a": 1, "b": 1, "c": 1})
    cfg = {"cuantiles": CUANTILES, "semilla": 1, "bootstrap_repeticiones": 200}
    with pytest.raises(KeyError):
        ev.seleccionar(tabla, pred, ["ingenuo"], cfg)              # sin bloque no hay regla
    sel = ev.seleccionar(tabla, pred, ["ingenuo"], cfg | {"bootstrap_bloque": 3})
    assert sel[1]["bloque"] == 3
    assert all(c["bloque"] == 3 for c in sel[1]["candidatos"])


def test_regla_de_despliegue_tal_como_esta_escrita(monkeypatch):
    """config/modelos.yaml: «se despliega el modelo de menor pérdida de cuantiles en validación SOLO si
    mejora a la mejor línea base con IC 90 % > 0. Si no, se usa la línea base». Si el de menor pérdida no
    es significativo, no se rescata al segundo."""
    tabla = pd.DataFrame([
        {"modelo": "ingenuo", "h": 1, "pinball": 0.050},
        {"modelo": "perfil", "h": 1, "pinball": 0.052},
        {"modelo": "lightgbm", "h": 1, "pinball": 0.040},       # el mejor, pero su IC cruza el cero
        {"modelo": "sarimax", "h": 1, "pinball": 0.045},        # segundo, con IC > 0
    ])
    ic = {"lightgbm": (0.20, -0.01, 0.40), "sarimax": (0.10, 0.02, 0.18)}
    monkeypatch.setattr(metricas, "bootstrap_mejora", lambda a, b, *args, **kw: ic[a["modelo"].iloc[0]])
    pred = pd.DataFrame({"modelo": ["ingenuo", "perfil", "lightgbm", "sarimax"], "h": 1})
    cfg = {"cuantiles": CUANTILES, "semilla": 1, "bootstrap_repeticiones": 10, "bootstrap_bloque": 3}
    sel = ev.seleccionar(tabla, pred, ["ingenuo", "perfil"], cfg)
    assert sel[1]["modelo"] == "ingenuo"
    assert sel[1]["mejor_modelo"] == "lightgbm"

    ic["lightgbm"] = (0.20, 0.01, 0.40)                          # ahora sí significativo
    assert ev.seleccionar(tabla, pred, ["ingenuo", "perfil"], cfg)[1]["modelo"] == "lightgbm"


def test_si_una_linea_base_es_la_mejor_se_despliega_la_linea_base(monkeypatch):
    tabla = pd.DataFrame([{"modelo": "ingenuo", "h": 1, "pinball": 0.030},
                          {"modelo": "lightgbm", "h": 1, "pinball": 0.031}])
    monkeypatch.setattr(metricas, "bootstrap_mejora", lambda *a, **k: (-0.03, -0.05, -0.01))
    pred = pd.DataFrame({"modelo": ["ingenuo", "lightgbm"], "h": 1})
    cfg = {"cuantiles": CUANTILES, "semilla": 1, "bootstrap_repeticiones": 10, "bootstrap_bloque": 3}
    assert ev.seleccionar(tabla, pred, ["ingenuo"], cfg)[1]["modelo"] == "ingenuo"


# ------------------------------------------------------------------ hallazgo 7 (no está en las correcciones)

@pytest.mark.xfail(strict=True, reason="Hallazgo 7 de la auditoría: pendiente, no forma parte de las "
                                       "correcciones a–c. Al corregirlo, quitar esta marca.")
def test_salto_extremo_a_traves_de_un_hueco_tambien_se_reporta():
    regs = [_reg("Coliflor", 2400, dt.date(2017, 7, 1)), _reg("Coliflor", 650, dt.date(2017, 10, 1))]
    _, cal = panel.construir(regs, _catalogo())
    assert len(cal.saltos_extremos) == 1


# ------------------------------------------------------------------ A3: calidad.json (solo reporte, el panel no cambia)

def _fecha(a, m):
    return dt.date(a, m, 1)


def test_salto_con_hueco_se_reporta_aparte_sin_tocar_el_precio():
    """El reporte nuevo vive en `saltos_con_hueco`; `saltos_extremos` (meses consecutivos) no cambia, y por eso
    el fallo esperado del hallazgo 7 conserva su explicación."""
    regs = [_reg("Coliflor", 2400, _fecha(2017, 7)), _reg("Coliflor", 650, _fecha(2017, 10))]
    precios, cal = panel.construir(regs, _catalogo())
    assert [p.precio for p in precios] == [2400, 650]
    assert cal.saltos_extremos == []
    assert len(cal.saltos_con_hueco) == 1
    s = cal.saltos_con_hueco[0]
    assert (s["desde"], s["hasta"], s["meses_de_hueco"]) == ("2017-07-01", "2017-10-01", 2)
    assert (s["precio_antes"], s["precio_despues"]) == (2400, 650)


def test_salto_con_hueco_no_duplica_el_de_meses_consecutivos():
    regs = [_reg("Cilantro", 1000, _fecha(2024, 1)), _reg("Cilantro", 3500, _fecha(2024, 2)),
            _reg("Cilantro", 3400, _fecha(2024, 4))]
    _, cal = panel.construir(regs, _catalogo())
    assert len(cal.saltos_extremos) == 1 and cal.saltos_con_hueco == []


def test_dato_aislado_diez_veces_distinto_de_sus_dos_vecinos_es_sospechoso_y_se_conserva():
    """Caso real de Paloquemao (pastas alimenticias): 8.222 → 394 → 9.600 $/kg."""
    regs = [_reg("Pastas", 8222, _fecha(2022, 5)), _reg("Pastas", 394, _fecha(2024, 2)),
            _reg("Pastas", 9600, _fecha(2024, 3))]
    precios, cal = panel.construir(regs, _catalogo())
    assert [p.precio for p in precios] == [8222, 394, 9600]        # no se borra ni se corrige
    assert len(cal.datos_sospechosos) == 1
    d = cal.datos_sospechosos[0]
    assert (d["fecha"], d["precio"], d["precio_anterior"], d["precio_siguiente"]) == ("2024-02-01", 394, 8222, 9600)
    assert d["razon_anterior"] == pytest.approx(394 / 8222) and d["razon_siguiente"] == pytest.approx(9600 / 394)


def test_un_salto_grande_que_se_mantiene_no_es_dato_sospechoso():
    regs = [_reg("Pastas", 394, _fecha(2024, 1)), _reg("Pastas", 9600, _fecha(2024, 2)), _reg("Pastas", 9500, _fecha(2024, 3))]
    _, cal = panel.construir(regs, _catalogo())
    assert cal.datos_sospechosos == []                              # cambio de nivel, no un valor aislado
    regs = [_reg("Cilantro", 1000, _fecha(2024, 1)), _reg("Cilantro", 3500, _fecha(2024, 2)), _reg("Cilantro", 1000, _fecha(2024, 3))]
    _, cal = panel.construir(regs, _catalogo())
    assert cal.datos_sospechosos == [] and len(cal.saltos_extremos) == 2    # ×3,5: se reporta como salto, no como sospechoso


def test_calidad_json_incluye_los_reportes_nuevos(tmp_path):
    from mercado_al_dia import proceso
    from test_fase1 import _proyecto as _proyecto_fase1

    raiz = _proyecto_fase1(tmp_path)
    proceso.ejecutar(raiz, decir=lambda *_: None)
    datos = json.loads((raiz / "data" / "procesado" / "calidad.json").read_text(encoding="utf-8"))
    assert datos["saltos_con_hueco"] == [] and datos["datos_sospechosos"] == []
