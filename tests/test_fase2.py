"""Pruebas de la fase 2 sin internet: datos sintéticos con temporada, tendencia y saltos conocidos."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest
import yaml

from mercado_al_dia import mineria, pronostico
from mercado_al_dia.modelos import evaluacion as ev
from mercado_al_dia.modelos import familias, metricas
from mercado_al_dia.modelos.datos import Datos, leer_oni

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((RAIZ_PROYECTO / "config" / "modelos.yaml").read_text(encoding="utf-8"))


def _cfg_rapida():
    c = copy.deepcopy(CFG)
    c["lightgbm"] = {**c["lightgbm"], "n_estimators": 40}
    c["meses_minimos_entrenamiento"] = 60
    c["validacion"] = {"desde": "2018-01", "hasta": "2018-12"}
    c["prueba"] = {"desde": "2019-01", "hasta": "2020-09"}
    c["bootstrap_repeticiones"] = 200
    c["nbeats"] = {**c["nbeats"], "pasos": 20, "ancho": 16}
    return c


def _datos(n_prod=6, meses=96, semilla=1) -> Datos:
    rng = np.random.default_rng(semilla)
    idx = pd.period_range("2013-01", periods=meses, freq="M")
    cols = {}
    comun = rng.normal(0, 0.03, meses).cumsum()
    for j in range(n_prod):
        amp = 0.05 + 0.03 * j
        temporada = amp * np.sin(2 * np.pi * (idx.month - 1) / 12 + j)
        propio = rng.normal(0, 0.02, meses).cumsum()
        cols[f"p{j}"] = np.log(1000 * (j + 1)) + 0.004 * np.arange(meses) + temporada + (comun if j < 3 else propio)
    logp = pd.DataFrame(cols, index=idx)
    oni = pd.Series(np.sin(np.arange(-12, meses + 12) / 9), index=pd.period_range("2012-01", periods=meses + 24, freq="M"))
    abast = pd.Series(np.log(3e5) + rng.normal(0, 0.05, meses), index=idx)
    nombres = {c: c.upper() for c in cols}
    return Datos(logp, nombres, {c: "G" for c in cols}, {c: "kg" for c in cols}, oni, abast, list(cols), list(cols))


# ------------------------------------------------------------------ sin fuga de información

FAMILIAS_RAPIDAS = [familias.Ingenuo, familias.EstacionalAjustado, familias.PerfilEstacional, familias.LightGBMGlobal]


@pytest.mark.parametrize("clase", FAMILIAS_RAPIDAS)
def test_ningun_modelo_mira_el_futuro(clase):
    """Cambiar todo lo posterior al origen no puede cambiar el pronóstico hecho en el origen."""
    cfg = _cfg_rapida()
    d = _datos(meses=120)
    origen = pd.Period("2020-06", "M")
    a = clase(cfg)
    a.ajustar(d, origen)
    pa = pd.DataFrame(a.predecir(d, origen, d.evaluacion)).set_index(["pid", "h"])

    d2 = copy.deepcopy(d)
    d2.logp.loc[origen + 1:] += 3.0                               # el futuro se dispara
    d2.abastecimiento.loc[origen:] -= 1.0                          # y el abastecimiento del mes t también
    b = clase(cfg)
    b.ajustar(d2, origen)
    pb = pd.DataFrame(b.predecir(d2, origen, d2.evaluacion)).set_index(["pid", "h"])
    assert len(pa) == len(d.evaluacion) * 3
    pd.testing.assert_frame_equal(pa.sort_index(), pb.sort_index())


def test_caracteristicas_usan_exogenas_con_rezago():
    d = _datos()
    t = familias.caracteristicas(d, 1, CFG)
    fila = t[(t["mes"] == pd.Period("2016-05", "M")) & (t["pid"] == "p0")].iloc[0]
    assert fila["oni"] == pytest.approx(d.oni[pd.Period("2016-03", "M")])          # rezago 2
    esperado = d.abastecimiento[pd.Period("2016-04", "M")] - d.abastecimiento[pd.Period("2015-04", "M")]
    assert fila["abast_anual"] == pytest.approx(esperado)                           # rezago 1


def test_cuantiles_nunca_se_cruzan():
    cfg = _cfg_rapida()
    d = _datos()
    m = familias.LightGBMGlobal(cfg)
    m.ajustar(d, pd.Period("2018-01", "M"))
    for f in m.predecir(d, pd.Period("2018-01", "M"), d.evaluacion):
        assert f["q10"] <= f["q50"] <= f["q90"]


# ------------------------------------------------------------------ evaluación

def test_cqr_lleva_la_cobertura_al_objetivo():
    rng = np.random.default_rng(3)
    y = rng.normal(0, 1, 2000)
    p = pd.DataFrame({"h": 1, "y": y, "q10": -0.3, "q50": 0.0, "q90": 0.3})       # intervalo demasiado estrecho
    assert ((p.y >= p.q10) & (p.y <= p.q90)).mean() < 0.3
    c = ev.aplicar_cqr(p, ev.cqr(p, 0.8))
    assert ((c.y >= c.q10) & (c.y <= c.q90)).mean() >= 0.8


def _pred(modelo, ruido, n_origen=24, semilla=0):
    rng = np.random.default_rng(semilla)
    filas = []
    for o in range(n_origen):
        for pid in ("a", "b", "c"):
            y = rng.normal()
            e = rng.normal(0, ruido)
            filas.append({"modelo": modelo, "pid": pid, "origen": f"o{o}", "h": 1, "y": y, "base": 0.0,
                          "q10": y + e - 1.28, "q50": y + e, "q90": y + e + 1.28})
    return pd.DataFrame(filas)


def test_bootstrap_distingue_mejora_real_de_ruido():
    bueno, malo = _pred("m", 0.2), _pred("b", 1.5)
    mej, lo, hi = metricas.bootstrap_mejora(bueno, malo, [0.1, 0.5, 0.9], 500, 1)
    assert mej > 0 and lo > 0
    mej, lo, hi = metricas.bootstrap_mejora(malo, malo.assign(modelo="x"), [0.1, 0.5, 0.9], 500, 1)
    assert mej == pytest.approx(0) and lo <= 0 <= hi


def test_seleccion_se_queda_con_la_linea_base_si_la_mejora_no_es_significativa():
    base = _pred("ingenuo", 1.0, semilla=5)
    ruido = np.random.default_rng(11).normal(0, 0.3, len(base))       # otro modelo, igual de bueno en promedio
    casi = base.assign(modelo="lightgbm", q10=base["q10"] + ruido, q50=base["q50"] + ruido, q90=base["q90"] + ruido)
    pred = pd.concat([base, casi])
    tabla = ev.tabla_metricas(pred, {"cuantiles": [0.1, 0.5, 0.9]}, {"a": 1, "b": 1, "c": 1})
    sel = ev.seleccionar(tabla, pred, ["ingenuo"], {"cuantiles": [0.1, 0.5, 0.9], "semilla": 1, "bootstrap_repeticiones": 300,
                                                       "bootstrap_bloque": CFG["bootstrap_bloque"]})
    assert sel[1]["modelo"] == "ingenuo"


def test_metricas_en_log_no_castigan_la_inflacion():
    p = pd.DataFrame({"pid": ["a"] * 2, "h": [1, 1], "y": [math.log(1000), math.log(100000)],
                      "q10": [math.log(900), math.log(90000)], "q50": [math.log(1000), math.log(100000)],
                      "q90": [math.log(1100), math.log(110000)], "base": [math.log(1000), math.log(100000)]})
    r = metricas.resumen(p, [0.1, 0.5, 0.9], {"a": 0.05})
    assert r["mae_pct"] == 0 and r["mase"] == 0 and r["cobertura"] == 1 and r["acierto_direccion"] is None


# ------------------------------------------------------------------ experimento completo y prueba única

def _proyecto(tmp_path: Path, cfg: dict) -> Path:
    raiz = tmp_path / "proy"
    (raiz / "config").mkdir(parents=True)
    d = _datos()
    nombres = {c: f"Producto {i}" for i, c in enumerate(d.logp.columns)}
    with open(raiz / "config" / "modelos.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg | {"productos_evaluacion": list(nombres.values())}, f, allow_unicode=True)
    (raiz / "config" / "productos.yaml").write_text(
        (RAIZ_PROYECTO / "config" / "productos.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    proc = raiz / "data" / "procesado"
    proc.mkdir(parents=True)
    filas = ["fecha,grupo,producto,producto_id,unidad,mercado,precio,producto_original,archivo,hoja,fila,sha256"]
    for c, n in nombres.items():
        for mes, v in d.logp[c].items():
            filas.append(f"{mes},G,{n},{n.lower()},kg,\"Bogotá, D.C., Corabastos\",{math.exp(v):.2f},{n},x,h,1,0")
    (proc / "precios_bogota.csv").write_text("\n".join(filas) + "\n", encoding="utf-8")
    ex = raiz / "data" / "raw" / "exogenas"
    ex.mkdir(parents=True)
    temporadas = list(__import__("mercado_al_dia.modelos.datos", fromlist=["TEMPORADAS"]).TEMPORADAS)
    lineas = ["  SEAS  YR   TOTAL   ANOM"] + [f"  {temporadas[k % 12]} {2010 + k // 12}  27.00  {math.sin(k / 9):.2f}" for k in range(12 * 14)]
    (ex / "noaa_oni.ascii.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    ab = raiz / "data" / "raw" / "sipsa" / "abastecimiento"
    ab.mkdir(parents=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2. Serie mensual"
    ws.append(["Fecha", "TOTAL", "Bogotá, D.C., Corabastos"])
    for mes in d.logp.index:
        ws.append([mes.to_timestamp().to_pydatetime(), 1e6, 3e5])
    wb.save(ab / "sipsa_a_series_historicas_2013_2026.xlsx")
    return raiz


def test_experimento_exige_validacion_y_usa_la_prueba_una_sola_vez(tmp_path):
    from mercado_al_dia.modelos import experimento

    raiz = _proyecto(tmp_path, _cfg_rapida())
    with pytest.raises(RuntimeError, match="validación"):
        experimento.correr(raiz, "prueba", con_nbeats=False, decir=lambda *_: None)
    v = experimento.correr(raiz, "validacion", con_nbeats=False, decir=lambda *_: None)
    assert set(v["seleccion"]) == {1, 2, 3}
    assert v["casos_comunes"] > 0
    p = experimento.correr(raiz, "prueba", con_nbeats=False, decir=lambda *_: None)
    assert p["seleccion_usada"] == json.loads(json.dumps(v["seleccion"]))
    with pytest.raises(RuntimeError, match="una sola vez"):
        experimento.correr(raiz, "prueba", con_nbeats=False, decir=lambda *_: None)
    # El pronóstico de producción usa la selección y queda ordenado y en pesos.
    r = pronostico.pronosticar(raiz)
    assert r.filas and all(f["q10"] <= f["q50"] <= f["q90"] for f in r.filas)
    assert {f["h"] for f in r.filas} == {1, 2, 3}


def test_cambiar_la_configuracion_invalida_la_seleccion(tmp_path):
    from mercado_al_dia.modelos import experimento

    cfg = _cfg_rapida()
    raiz = _proyecto(tmp_path, cfg)
    experimento.correr(raiz, "validacion", con_nbeats=False, decir=lambda *_: None)
    otra = yaml.safe_load((raiz / "config" / "modelos.yaml").read_text(encoding="utf-8")) | {"semilla": 99}
    (raiz / "config" / "modelos.yaml").write_text(yaml.safe_dump(otra, allow_unicode=True), encoding="utf-8")
    with pytest.raises(RuntimeError, match="cambiaron"):
        experimento.correr(raiz, "prueba", con_nbeats=False, decir=lambda *_: None)
    assert pronostico.pronosticar(raiz).motivo_ausente


def test_nbeats_entrena_y_respeta_el_orden_de_cuantiles():
    pytest.importorskip("jax")
    from mercado_al_dia.modelos.nbeats import NBeats

    cfg = _cfg_rapida()
    d = _datos()
    m = NBeats(cfg)
    m.ajustar(d, pd.Period("2018-01", "M"))
    salida = m.predecir(d, pd.Period("2018-01", "M"), d.evaluacion)
    assert len(salida) == len(d.evaluacion) * 3
    assert all(f["q10"] <= f["q50"] <= f["q90"] for f in salida)


# ------------------------------------------------------------------ minería y alertas

def test_vecinos_encuentran_a_los_que_comparten_choques():
    g = mineria.agrupar(_datos(meses=150).logp, minimo_meses=100, min_comunes=60)
    for p in ("p0", "p1", "p2"):
        assert {v for v, _ in g.vecinos[p][:2]} == {"p0", "p1", "p2"} - {p}
    assert g.etiqueta["p0"] == g.etiqueta["p1"] == g.etiqueta["p2"]


def test_cambio_de_nivel_se_detecta_cerca_de_donde_ocurre():
    idx = pd.period_range("2013-01", periods=120, freq="M")
    rng = np.random.default_rng(2)
    s = np.log(2000) + rng.normal(0, 0.03, 120)
    s[80:] += math.log(1.5)                                     # +50 % desde septiembre de 2019
    c = mineria.cambios_de_nivel(pd.DataFrame({"x": s}, index=idx), ["x"])["x"]
    assert abs((pd.Period(c.fecha, "M") - pd.Period("2019-09", "M")).n) <= 1
    assert c.cambio == pytest.approx(0.5, abs=0.08)


def test_alertas_para_tenderos():
    p = pronostico.Pronostico("2026-10", [
        {"pid": "a", "h": 1, "mes": "2026-11", "q10": 1100, "q50": 1200, "q90": 1300, "actual": 1000, "modelo": "m"},
        {"pid": "b", "h": 1, "mes": "2026-11", "q10": 800, "q50": 1080, "q90": 1300, "actual": 1000, "modelo": "m"},
        {"pid": "c", "h": 1, "mes": "2026-11", "q10": 900, "q50": 1010, "q90": 1100, "actual": 1000, "modelo": "m"},
        {"pid": "d", "h": 2, "mes": "2026-12", "q10": 2000, "q50": 2100, "q90": 2200, "actual": 1000, "modelo": "m"},
    ], {1: "m"}, None)
    a = pronostico.alertas(p, {}, {"cambio_minimo": 0.05})
    assert [(x["pid"], x["nivel"]) for x in a] == [("a", "alza_segura"), ("b", "alza_probable")]


def test_oni_se_asigna_al_mes_central(tmp_path):
    f = tmp_path / "oni.txt"
    f.write_text(" SEAS  YR   TOTAL   ANOM\n  DJF 2020  27.0  0.50\n  NDJ 2020  27.0  -1.10\n", encoding="utf-8")
    s = leer_oni(f)
    assert s[pd.Period("2020-01", "M")] == 0.5 and s[pd.Period("2020-12", "M")] == -1.1


def test_bootstrap_por_bloques_es_mas_ancho_con_autocorrelacion():
    rng = np.random.default_rng(4)
    n = 60
    choque = np.convolve(rng.normal(0, 1, n + 5), np.ones(6) / 6, mode="valid")[:n]   # ventaja persistente
    filas_m, filas_b = [], []
    for o in range(n):
        v = 0.9 + 0.3 * choque[o]                       # el "bueno" gana o pierde por rachas de meses
        for pid in ("a", "b"):
            base = {"pid": pid, "origen": f"o{o:02d}", "h": 1, "y": 0.0, "base": 0.0}
            filas_m.append(base | {"q10": 1.0, "q50": 1.0, "q90": 1.0})
            filas_b.append(base | {"q10": v, "q50": v, "q90": v})
    malo, bueno = pd.DataFrame(filas_m), pd.DataFrame(filas_b)
    _, lo1, hi1 = metricas.bootstrap_mejora(bueno, malo, [0.1, 0.5, 0.9], 1000, 1, bloque=1)
    _, lo6, hi6 = metricas.bootstrap_mejora(bueno, malo, [0.1, 0.5, 0.9], 1000, 1, bloque=6)
    assert (hi6 - lo6) > (hi1 - lo1)


def test_umbral_nulo_evita_falsas_alarmas_y_deja_pasar_un_cambio_real():
    idx = pd.period_range("2013-01", periods=150, freq="M")
    rng = np.random.default_rng(8)
    ar = np.zeros(150)
    for t in range(1, 150):
        ar[t] = 0.95 * ar[t - 1] + rng.normal(0, 0.05)
    escalon = np.log(2000) + rng.normal(0, 0.03, 150)
    escalon[135:] += math.log(1.6)                                 # +60 % hace 15 meses
    logp = pd.DataFrame({"ar": np.log(2000) + ar, "escalon": escalon}, index=idx)
    u = mineria.umbral_nulo(logp, ["ar", "escalon"], 24, simulaciones=100, semilla=3)
    c = mineria.cambios_de_nivel(logp, ["escalon"])["escalon"]
    assert abs(c.cambio) > u["escalon"]                             # el cambio real supera su umbral
    assert u["ar"] > 0.1                                            # el AR persistente exige un umbral alto


def test_fase2_lee_el_panel_recien_escrito(tmp_path, monkeypatch):
    """Regresión de la revisión independiente: la fase 2 no puede leer el CSV de la corrida anterior."""
    from mercado_al_dia import proceso
    import test_fase1

    raiz = test_fase1._proyecto(tmp_path)
    viejo = raiz / "data" / "procesado"
    viejo.mkdir(parents=True)
    (viejo / "precios_bogota.csv").write_text("fecha,producto\n2001-01,Viejo\n", encoding="utf-8")
    visto = {}

    def espia(r, cfg_an, decir=print):
        txt = (r / "data" / "procesado" / "precios_bogota.csv").read_text(encoding="utf-8-sig")
        visto["ultima"] = txt.strip().splitlines()[-1][:7]
        return {"pagina": {}, "tablas": {}, "resumen": {}}

    monkeypatch.setattr(proceso, "fase2", espia)
    r = proceso.ejecutar(raiz, decir=lambda *_: None)
    assert visto["ultima"] != "2001-01"
    assert r["mes"] == "2025-12"
