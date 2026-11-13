"""Pruebas de la fase 1 sin internet: Excel sintéticos con los formatos reales del DANE."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import openpyxl
import pytest
import yaml

from mercado_al_dia import analisis as A
from mercado_al_dia import proceso
from mercado_al_dia.sipsa import lector, panel

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
NOTA = "* Los precios reportados para los huevos y el bocadillo son $/unidad y los del aceite, el vinagre y el jugo de frutas $/litro."


def _excel(ruta: Path, hojas: dict[str, tuple[int, list[str], list[list]]], extra: list[str] = ()) -> Path:
    """hojas: nombre -> (fila del encabezado, encabezado, filas de datos)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nombre in extra:
        wb.create_sheet(nombre).append(["Índice", "Contenido"])
    for nombre, (fila_enc, enc, datos) in hojas.items():
        ws = wb.create_sheet(nombre)
        ws.append(["SISTEMA DE INFORMACIÓN DE PRECIOS Y ABASTECIMIENTO"])
        for _ in range(fila_enc - 2):
            ws.append([])
        ws.append(enc)
        for d in datos:
            ws.append(d)
        ws.append([])
        ws.append([NOTA])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta


def _mes(a, m):
    return dt.datetime(a, m, 1)


# ------------------------------------------------------------------ lector

def test_lee_los_tres_formatos_del_dane(tmp_path):
    raw = tmp_path / "data" / "raw"
    c = raw / "sipsa" / "precios_mensual"
    # 2013–2017: una hoja por año, "Fuente", "Precio", encabezado en la fila 10.
    _excel(c / "a.xlsx", {"1.1": (10, ["Fecha", "Grupo", "Producto", "Fuente", "Precio "],
                                  [[_mes(2013, 1), "FRUTAS", "Mora de Castilla", "Bogotá, D.C., Corabastos", 3000]])},
           extra=["Índice"])
    # 2020: una hoja por mes, "Mercado", "Precio  por kilogramo*", encabezado en la fila 7.
    _excel(c / "b.xlsx", {"Ene 20": (7, ["Fecha", "Grupo", "Producto", "Mercado", "Precio  por kilogramo*"],
                                     [[_mes(2020, 1), "FRUTAS", "Mora  de Castilla", "Bogotá, D.C., Corabastos", "3.500"]])})
    # 2026: hoja única con códigos, encabezado en la fila 6.
    _excel(c / "c.xlsx", {"2026": (6, ["Fecha", "Grupo", "Producto", "Código CPC", "Mercado", "Departamento",
                                       "Código departamento", "Municipio", "Código municipio", "Precio promedio por kilogramo*"],
                                   [[_mes(2026, 1), "FRUTAS", "Mora de Castilla", "0134", "Bogotá, D.C., Corabastos",
                                     "BOGOTÁ, D.C.", "11", "BOGOTÁ, D.C.", "11001", 4100]])},
           extra=["CPC"])
    inc: list = []
    regs = list(lector.leer_carpeta(c, raw, inc))
    assert [(r.fecha.year, r.precio) for r in regs] == [(2013, 3000.0), (2020, 3500.0), (2026, 4100.0)]
    assert regs[1].producto == "Mora de Castilla"          # espacios dobles normalizados
    assert regs[2].cpc == "0134"
    assert (regs[0].archivo, regs[0].hoja, regs[0].fila) == ("sipsa/precios_mensual/a.xlsx", "1.1", 11)
    assert len(regs[0].sha256) == 64
    assert inc == []                                        # la nota al pie no es una incidencia


def test_precio_vacio_o_cero_se_reporta_y_no_se_inventa(tmp_path):
    raw = tmp_path / "raw"
    _excel(raw / "x.xlsx", {"2024": (6, ["Fecha", "Grupo", "Producto", "Mercado", "Precio promedio por kilogramo*"],
                                     [[_mes(2024, 1), "FRUTAS", "Lulo", "Bogotá, D.C., Corabastos", None],
                                      [_mes(2024, 1), "FRUTAS", "Coco", "Bogotá, D.C., Corabastos", 0],
                                      [_mes(2024, 1), "FRUTAS", "Kiwi", "Bogotá, D.C., Corabastos", 9000]])})
    inc: list = []
    regs = list(lector.leer_carpeta(raw, raw, inc))
    assert [r.producto for r in regs] == ["Kiwi"]
    assert [i.motivo for i in inc] == ["precio vacío o no positivo"] * 2


def test_hoja_con_columnas_irreconocibles_falla_con_mensaje(tmp_path):
    raw = tmp_path / "raw"
    _excel(raw / "x.xlsx", {"2024": (6, ["Fecha", "Producto", "Valor"], [[_mes(2024, 1), "Kiwi", 9000]])})
    with pytest.raises(lector.FormatoDesconocido, match="faltan columnas"):
        list(lector.leer_carpeta(raw, raw))


@pytest.mark.parametrize("texto, esperado", [("3.500", 3500.0), ("1.234,5", 1234.5), (" 980 ", 980.0), ("-", None), ("n.d.", None)])
def test_precio_en_texto(texto, esperado):
    assert lector._precio(texto) == esperado


# ------------------------------------------------------------------ panel

def _reg(producto, precio, fecha=dt.date(2024, 1, 1), mercado="Bogotá, D.C., Corabastos", grupo="FRUTAS", fila=1):
    return lector.Registro(fecha, grupo, producto, mercado, precio, "", "f.xlsx", "h", fila, "0" * 64)


def _catalogo():
    return panel.Catalogo(yaml.safe_load((RAIZ_PROYECTO / "config" / "productos.yaml").read_text(encoding="utf-8")))


def test_unidades_segun_la_nota_al_pie_del_dane():
    cat = _catalogo()
    assert cat.unidad(lector.plano("Huevo rojo A")) == "unidad"
    assert cat.unidad(lector.plano("Bocadillo veleño")) == "unidad"
    assert cat.unidad(lector.plano("Aceite vegetal mezcla")) == "litro"
    assert cat.unidad(lector.plano("Papa parda pastusa")) == "kg"


def test_equivalencias_y_variantes_de_mercado():
    regs = [_reg("Galletas saladas 3 tacos", 100, dt.date(2015, 7, 1), grupo="PROCESADOS"),
            _reg("Galletas saladas", 110, dt.date(2015, 8, 1), grupo="PROCESADOS"),
            _reg("Pechuga", 9000, mercado="Bogotá, D.C., Frigorífico Ble Ltda.", grupo="CARNES"),
            _reg("Pechuga", 9100, dt.date(2024, 2, 1), mercado="Bogotá, D.C., Frigorífico Ble Ltda,", grupo="CARNES"),
            _reg("Lulo", 5000, mercado="Medellín, Central Mayorista")]          # fuera de Bogotá: no se guarda
    precios, cal = panel.construir(regs, _catalogo())
    assert {p.producto for p in precios} == {"Galletas saladas", "Pechuga"}
    assert cal.equivalencias_aplicadas == {"Galletas saladas 3 tacos": 1}
    assert len({p.mercado_id for p in precios if p.producto == "Pechuga"}) == 1
    assert cal.registros_leidos == 5


def test_grupo_se_muestra_con_tildes():
    regs = [_reg("Papa", 1000, grupo="TUBERCULOS, RAICES Y PLATANOS"),
            _reg("Papa", 1100, dt.date(2024, 2, 1), grupo="TUBÉRCULOS, RAÍCES Y PLÁTANOS")]
    precios, _ = panel.construir(regs, _catalogo())
    assert {p.grupo for p in precios} == {"TUBÉRCULOS, RAÍCES Y PLÁTANOS"}


def test_duplicados_iguales_se_unen_y_en_conflicto_se_descartan():
    regs = [_reg("Lulo", 5000), _reg("Lulo", 5000, fila=2),
            _reg("Coco", 3000), _reg("Coco", 3300, fila=2)]
    precios, cal = panel.construir(regs, _catalogo())
    assert [p.producto for p in precios] == ["Lulo"]
    assert cal.duplicados_identicos == 1
    assert cal.duplicados_en_conflicto[0]["precios"] == [3000.0, 3300.0]


def test_salto_extremo_se_reporta_sin_tocar_el_precio():
    regs = [_reg("Cilantro", 1000), _reg("Cilantro", 3500, dt.date(2024, 2, 1))]
    precios, cal = panel.construir(regs, _catalogo())
    assert [p.precio for p in precios] == [1000, 3500]
    assert len(cal.saltos_extremos) == 1


# ------------------------------------------------------------------ análisis

def _serie_estacional(anios=10, amplitud=0.2, tendencia=0.005, inicio=2013, ruido=None):
    s = {}
    for k in range(anios * 12):
        i = inicio * 12 + k
        v = math.log(2000) + tendencia * k + amplitud * math.sin(2 * math.pi * (i % 12) / 12)
        if ruido:
            v += ruido[k % len(ruido)]
        s[i] = math.exp(v)
    return s


def test_perfil_recupera_la_temporada_de_una_senal_conocida():
    p = A.perfil(_serie_estacional(), anios_minimos=5)
    esperado = [0.2 * math.sin(2 * math.pi * m / 12) for m in range(12)]
    assert max(abs(a - b) for a, b in zip(p.efecto, esperado)) < 0.02
    assert abs(sum(p.efecto)) < 1e-9                       # centrado


def test_perfil_no_usa_datos_del_futuro():
    s = _serie_estacional()
    corte = min(s) + 84
    antes = A.perfil(s, hasta=corte)
    s2 = dict(s)
    for i in s2:
        if i >= corte:
            s2[i] *= 50                                     # el futuro cambia por completo
    assert A.perfil(s2, hasta=corte).efecto == antes.efecto


def test_sin_anios_suficientes_no_hay_perfil_ni_consejo():
    p = A.perfil(_serie_estacional(anios=4), anios_minimos=5)
    assert p is None and A.consejo(p, 0, 0.03, 2.0) == 0


def test_validacion_acierta_en_serie_estacional_y_no_en_ruido():
    estacional = {"x": _serie_estacional(anios=12, ruido=[0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.0])}
    v = A.validar(estacional, 2018 * 12, 0.03, 2.0, 5)
    assert v.evaluados > 20 and v.tasa > 0.9
    lo, hi = v.intervalo()
    assert lo <= v.tasa <= hi
    import random
    rnd = random.Random(7)
    ruido = {"r": {2013 * 12 + k: 1000 * math.exp(rnd.gauss(0, 0.15)) for k in range(12 * 12)}}
    w = A.validar(ruido, 2018 * 12, 0.03, 2.0, 5)
    assert w.evaluados < v.evaluados                        # en ruido casi nunca da consejo


def test_indicadores_barato_caro_y_origen():
    s = {2023 * 12 + k: 1000.0 for k in range(40)}
    ultimo = max(s)
    s[ultimo] = 800.0
    precios = [panel.Precio(A.fecha_de(i), "FRUTAS", "lulo", "Lulo", "kg", "m", "M", v, "Lulo", "f.xlsx", "h", 9, "0")
               for i, v in s.items()]
    ind = A.indicadores({"lulo": s}, precios, "m", {"señales": {"umbral_barato_caro": 0.1, "meses_minimos_historia": 36}})
    assert ind[0].estado == "barato" and ind[0].variacion_12m == pytest.approx(-0.2)
    assert ind[0].origen == "f.xlsx#h!9"


def test_canasta_solo_suma_meses_completos():
    cat = _catalogo()
    e = 2024 * 12
    todas = {"arroz de primera": {e: 2000.0, e + 1: 2100.0}, "huevo rojo a": {e: 400.0}}
    precios = [panel.Precio(dt.date(2024, 1, 1), "G", "huevo rojo a", "Huevo rojo A", "unidad", "m", "M", 400, "", "", "", 0, "")]
    c = A.canasta(todas, precios, "m", {"productos": [{"producto": "Arroz de primera", "cantidad": 2},
                                                       {"producto": "Huevo rojo A", "cantidad": 30},
                                                       {"producto": "Inexistente", "cantidad": 1}]}, cat)
    assert c.costo == {e: 2000 * 2 + 400 * 30}
    assert c.faltantes == {"Huevo rojo A": ["2024-02"]}
    assert c.no_encontrados == ["Inexistente"]
    assert next(x for x in c.componentes if x["producto"] == "Huevo rojo A")["unidad"] == "unidad"


# ------------------------------------------------------------------ punta a punta

def _proyecto(tmp_path) -> Path:
    raiz = tmp_path / "proy"
    (raiz / "config").mkdir(parents=True)
    for n in ("productos.yaml", "analisis.yaml", "canasta.yaml"):
        (raiz / "config" / n).write_text((RAIZ_PROYECTO / "config" / n).read_text(encoding="utf-8"), encoding="utf-8")
    filas = []
    for k in range(10 * 12):
        a, m = 2016 + k // 12, k % 12 + 1
        for prod, base, amp in (("Arroz de primera", 2500, 0.02), ("Tomate chonto", 2000, 0.25), ("Huevo rojo A", 350, 0.05)):
            v = base * (1 + 0.004 * k) * math.exp(amp * math.sin(2 * math.pi * (m - 1) / 12))
            filas.append([_mes(a, m), "VERDURAS", prod, "Bogotá, D.C., Corabastos", round(v)])
            if prod == "Tomate chonto":
                filas.append([_mes(a, m), "VERDURAS", prod, "Bogotá, D.C., Paloquemao", round(v * 1.1)])
    _excel(raiz / "data" / "raw" / "sipsa" / "precios_mensual" / "sipsa_p_serie_mensual_2016_2025.xlsx",
           {"datos": (6, ["Fecha", "Grupo", "Producto", "Mercado", "Precio promedio por kilogramo*"], filas)})
    return raiz


def test_proceso_completo_genera_tablas_y_pagina(tmp_path):
    raiz = _proyecto(tmp_path)
    r = proceso.ejecutar(raiz, decir=lambda *_: None)
    salida = raiz / "data" / "procesado"
    assert r["mes"] == "2025-12" and r["productos_en_tablero"] == 3
    assert r["canasta"]["no_encontrados"]                  # la canasta real tiene más productos que el ejemplo
    for n in ("precios_bogota.csv", "indicadores_corabastos.csv", "validacion_estacional.csv", "canasta.csv", "calidad.json", "mercado.html"):
        assert (salida / n).exists(), n
    html = (salida / "mercado.html").read_text(encoding="utf-8")
    assert "Tomate chonto" in html and "/*DATOS*/" not in html
    datos = json.loads((salida / "calidad.json").read_text(encoding="utf-8"))
    assert datos["validacion_estacional"]["evaluados"] > 0


def test_crudo_alterado_detiene_el_proceso(tmp_path):
    raiz = _proyecto(tmp_path)
    x = next((raiz / "data" / "raw").rglob("*.xlsx"))
    (raiz / "data" / "manifest.json").write_text(json.dumps({"archivos": {
        x.relative_to(raiz / "data" / "raw").as_posix(): {"sha256": "0" * 64}}}), encoding="utf-8")
    with pytest.raises(proceso.CrudoAlterado):
        proceso.ejecutar(raiz, decir=lambda *_: None)
    assert proceso.main([str(raiz)]) == 2
