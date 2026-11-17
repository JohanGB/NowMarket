"""Mercado al Día de punta a punta, en un comando: ``python -m mercado_al_dia``.

1. Verifica que los crudos no cambiaron (SHA-256 contra ``data/manifest.json``).
2. Lee todos los Excel mensuales de SIPSA (los tres formatos del DANE).
3. Normaliza, aplica equivalencias y unidades, y mide la calidad.
4. Indicadores, temporada validada, canasta, minería (vecinos y cambios de nivel) y
   pronóstico con el modelo seleccionado en validación (``models/registro/seleccion.json``).
5. Escribe las tablas en ``data/procesado`` y la página ``data/procesado/mercado.html``.

El experimento de modelos (validación y prueba única) es aparte:
``python -m mercado_al_dia.modelos.experimento validacion|prueba``.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

from . import __version__, analisis, pagina
from .sipsa import lector, panel


class CrudoAlterado(RuntimeError):
    """Un archivo de data/raw no coincide con su huella del manifiesto."""


def _yaml(ruta: Path) -> dict:
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def verificar_crudos(raiz: Path, carpeta: Path) -> list[str]:
    """Compara cada Excel con el manifiesto. Devuelve avisos; lanza si alguno cambió."""
    ruta = raiz / "data" / "manifest.json"
    registrados = json.loads(ruta.read_text(encoding="utf-8")).get("archivos", {}) if ruta.exists() else {}
    avisos, alterados = [], []
    for x in sorted(carpeta.glob("*.xlsx")):
        rel = x.relative_to(raiz / "data" / "raw").as_posix()
        if rel not in registrados:
            avisos.append(f"{rel} no está en el manifiesto (se lee igual; regístrelo con el script de descarga)")
        elif registrados[rel]["sha256"] != lector.sha256_archivo(x):
            alterados.append(rel)
    if alterados:
        raise CrudoAlterado("Estos archivos cambiaron desde que se registraron y data/raw es inmutable: "
                            + ", ".join(alterados))
    return avisos


def _csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def ejecutar(raiz: Path, decir=print) -> dict:
    raiz = Path(raiz)
    carpeta = raiz / "data" / "raw" / "sipsa" / "precios_mensual"
    salida = raiz / "data" / "procesado"
    salida.mkdir(parents=True, exist_ok=True)
    cfg_prod = _yaml(raiz / "config" / "productos.yaml")
    cfg_an = _yaml(raiz / "config" / "analisis.yaml")
    cfg_can = _yaml(raiz / "config" / "canasta.yaml")

    decir("1/5 Verificando que los datos crudos no cambiaron")
    for a in verificar_crudos(raiz, carpeta):
        decir("  aviso: " + a)

    decir("2/5 Leyendo los Excel del DANE (puede tardar unos 30 segundos)")
    incidencias: list[lector.Incidencia] = []
    registros = lector.leer_carpeta(carpeta, raiz / "data" / "raw", incidencias)

    decir("3/5 Normalizando productos, unidades y mercados")
    catalogo = panel.Catalogo(cfg_prod)
    precios, calidad = panel.construir(registros, catalogo, incidencias)
    if not precios:
        raise RuntimeError("No se encontró ningún precio de los mercados configurados.")

    decir("4/5 Indicadores, temporada, validación y canasta")
    ref = analisis.series(precios, catalogo.referencia)
    if not ref:
        raise RuntimeError(f"No hay datos del mercado de referencia ({catalogo.referencia}).")
    comp = {}
    for m_id in catalogo.comparacion:
        s = analisis.series(precios, m_id)
        if s:
            nombre = next(p.mercado for p in precios if p.mercado_id == m_id)
            comp[nombre] = s
    est, val_cfg = cfg_an.get("estacionalidad", {}), cfg_an.get("validacion", {})
    anios_min, efecto, z = int(est.get("anios_minimos", 5)), float(est.get("efecto_minimo", 0.03)), float(est.get("z", 2.0))
    a, m = (int(x) for x in str(val_cfg.get("desde", "2018-01")).split("-"))
    validacion = analisis.validar(ref, analisis.indice(dt.date(a, m, 1)), efecto, z, anios_min)
    mostrar = (validacion.evaluados > 0 and validacion.tasa > validacion.tasa_base
               and validacion.tasa >= float(val_cfg.get("aciertos_minimos", 0.55)))
    indicadores = analisis.indicadores(ref, precios, catalogo.referencia, cfg_an)
    perfiles = {i.producto_id: analisis.perfil(ref[i.producto_id], anios_minimos=anios_min) for i in indicadores}
    canasta = analisis.canasta(ref, precios, catalogo.referencia, cfg_can, catalogo)

    # El panel se escribe ANTES de la fase 2: los modelos lo leen y deben ver el mes recién procesado.
    _csv(salida / "precios_bogota.csv", [vars(p) | {"fecha": p.fecha.isoformat()[:7]} for p in precios],
         ["fecha", "grupo", "producto", "producto_id", "unidad", "mercado", "precio", "producto_original",
          "archivo", "hoja", "fila", "sha256"])
    extras = fase2(raiz, cfg_an, decir)
    mes_fase1 = analisis.fecha_de(max(max(s) for s in ref.values())).isoformat()[:7]
    origen = extras["resumen"].get("origen")
    if origen and origen != mes_fase1:
        raise RuntimeError(f"El pronóstico parte de {origen} pero el tablero de {mes_fase1}: datos desalineados.")

    decir("5/5 Escribiendo tablas y página")
    _csv(salida / "indicadores_corabastos.csv", [vars(i) for i in indicadores], list(analisis.Indicador.__dataclass_fields__))
    _csv(salida / "validacion_estacional.csv",
         [{"producto_id": k, "evaluados": e, "aciertos": c, "tasa": round(c / e, 4)} for k, (e, c) in sorted(validacion.por_producto.items())],
         ["producto_id", "evaluados", "aciertos", "tasa"])
    _csv(salida / "canasta.csv", [{"mes": analisis.fecha_de(i).isoformat()[:7], "costo": round(v)} for i, v in sorted(canasta.costo.items())],
         ["mes", "costo"])
    lo, hi = validacion.intervalo()
    resumen = {
        "version": __version__, "generado": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "mes": indicadores[0].mes if indicadores else None, "mercado_referencia": catalogo.rotulo_referencia,
        "registros_leidos": calidad.registros_leidos, "registros_por_archivo": calidad.registros_por_archivo,
        "precios_guardados": len(precios), "productos_referencia": len(ref), "productos_en_tablero": len(indicadores),
        "duplicados_identicos": calidad.duplicados_identicos, "duplicados_en_conflicto": calidad.duplicados_en_conflicto,
        "equivalencias_aplicadas": calidad.equivalencias_aplicadas, "saltos_extremos": calidad.saltos_extremos,
        "saltos_con_hueco": calidad.saltos_con_hueco, "datos_sospechosos": calidad.datos_sospechosos,
        "incidencias": calidad.incidencias,
        "estados": {e: sum(1 for i in indicadores if i.estado == e) for e in ("barato", "normal", "caro", "sin_referencia")},
        "validacion_estacional": {"evaluados": validacion.evaluados, "aciertos": validacion.aciertos,
                                  "tasa": round(validacion.tasa, 4), "ic95": [round(lo, 4), round(hi, 4)],
                                  "linea_base": round(validacion.tasa_base, 4), "productos": validacion.productos,
                                  "periodo": [validacion.desde, validacion.hasta], "se_muestra": mostrar},
        "canasta": {"meses_completos": len(canasta.costo), "no_encontrados": canasta.no_encontrados,
                    "ultimo_costo": round(canasta.costo[max(canasta.costo)]) if canasta.costo else None},
    }
    (salida / "calidad.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html = pagina.construir(salida / "mercado.html", indicadores=indicadores, referencia=ref, comparacion=comp,
                            perfiles=perfiles, validacion=validacion, mostrar_consejo=mostrar, canasta=canasta,
                            rotulo=catalogo.rotulo_referencia, cfg_validacion=val_cfg, **extras["pagina"])
    for nombre, (filas, cols) in extras["tablas"].items():
        _csv(salida / nombre, filas, cols)
    resumen["fase2"] = extras["resumen"]
    (salida / "calidad.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resumen["pagina"] = str(html)
    return resumen


NOMBRES_MODELO = {"lightgbm": "LightGBM (aprendizaje automático)", "ingenuo": "Ingenuo calibrado (el precio se mantiene)",
                  "sarimax": "SARIMAX", "perfil_estacional": "Perfil estacional", "estacional_ajustado": "Estacional ajustado",
                  "nbeats": "N-BEATS"}


def fase2(raiz: Path, cfg_an: dict, decir=print) -> dict:
    """Minería y pronóstico. Si faltan las dependencias de modelos o la validación, la página sale sin pronóstico."""
    vacio = {"pagina": {}, "tablas": {}, "resumen": {"pronostico": "no disponible"}}
    try:
        from . import mineria, pronostico
        from .modelos.datos import cargar
    except ImportError as e:
        decir(f"  aviso: sin modelos ({e.name} no está instalado; pip install -e .)")
        return vacio
    if not (raiz / "config" / "modelos.yaml").exists():
        decir("  aviso: sin config/modelos.yaml; la página sale sin pronóstico ni minería")
        return vacio
    cfg_m = _yaml(raiz / "config" / "modelos.yaml")
    try:
        datos = cargar(raiz, cfg_m)
    except (FileNotFoundError, ValueError) as e:
        decir(f"  aviso: sin pronóstico ni minería ({e})")
        return vacio
    g = mineria.agrupar(datos.logp)
    rmin = float(cfg_an.get("vecinos", {}).get("correlacion_minima", 0.5))
    vecinos = {p: [{"id": o, "nombre": datos.nombres[o], "rho": r} for o, r in vs if r >= rmin] for p, vs in g.vecinos.items()}
    cn = cfg_an.get("cambios_de_nivel", {})
    recientes = int(cn.get("meses_recientes", 24))
    cambios_todos = mineria.cambios_de_nivel(datos.logp, datos.evaluacion)
    umbrales = mineria.umbral_nulo(datos.logp, datos.evaluacion, recientes,
                                   int(cn.get("simulaciones", 200)), float(cn.get("nivel", 0.95)), int(cfg_m["semilla"]))
    limite = datos.ultimo - recientes
    cambios = {p: {"fecha": c.fecha, "cambio": c.cambio, "umbral": umbrales[p]} for p, c in cambios_todos.items()
               if c and pd.Period(c.fecha, "M") > limite and abs(c.cambio) >= max(float(cn.get("cambio_minimo", 0.15)), umbrales[p])}
    p = pronostico.pronosticar(raiz, datos)
    if p.motivo_ausente:
        decir("  aviso: sin pronóstico (" + p.motivo_ausente + ")")
    pron = {}
    for f in p.filas:
        pron.setdefault(f["pid"], []).append({k: f[k] for k in ("h", "mes", "q10", "q50", "q90", "modelo")})
    for v in pron.values():
        v.sort(key=lambda x: x["h"])
    alertas = pronostico.alertas(p, datos.nombres, cfg_an.get("alertas_tenderos", {}))
    modelos = {}
    if p.prueba:
        filas = [r for r in p.prueba["metricas_calibradas"] if p.seleccion.get(int(r["h"])) == r["modelo"]]
        modelos["prueba"] = [{"h": int(r["h"]), "modelo": r["modelo"], "nombre": NOMBRES_MODELO.get(r["modelo"], r["modelo"]),
                              "corto": {"lightgbm": "LightGBM", "ingenuo": "Ingenuo calibrado"}.get(r["modelo"], r["modelo"]),
                              "mae_pct": r["mae_pct"], "cobertura": r["cobertura"]} for r in sorted(filas, key=lambda r: r["h"])]
        desde, hasta = cfg_m["prueba"]["desde"], cfg_m["prueba"]["hasta"]
        veces = ("Medido en la prueba ({d} a {h}; se repitió una vez por corrección de método, D-030)" if p.prueba.get("forzada")
                 else "Medido una sola vez en la prueba ({d} a {h})").format(d=desde, h=hasta)
        modelos["nota"] = (f"{veces}, con los 18 productos de la canasta. "
                           "A: meses hacia adelante. Error típico: diferencia media entre lo más probable y el precio real, en % del precio. "
                           "Cubrió: veces que el precio real cayó dentro del rango (la meta es 80 %). Ingenuo calibrado: "
                           "el precio se mantiene, con un rango medido en los errores pasados.")
        sel = ", ".join(f"{h} {'mes' if h == 1 else 'meses'}: {NOMBRES_MODELO.get(m, m)}" for h, m in sorted(p.seleccion.items()))
        modelos["resumen"] = (f"se eligió el método de cada horizonte en validación ({cfg_m['validacion']['desde']} a "
                              f"{cfg_m['validacion']['hasta']}) y solo se usa un modelo si mejora de forma significativa a la mejor "
                              f"línea base. Resultado: {sel}. Los rangos se calibraron para cubrir el 80 %.")
    decir(f"  minería: {g.k} grupos (silueta {g.silueta:.2f}); {sum(1 for v in vecinos.values() if v)} productos con vecinos; "
          f"{len(cambios)} cambios de nivel recientes; {len(p.filas)} pronósticos; {len(alertas)} alertas")
    sus = _yaml(raiz / "config" / "sustitutos.yaml").get("grupos", [])
    tablas = {
        "pronosticos.csv": ([{"producto": datos.nombres[f["pid"]], **f} for f in p.filas],
                            ["producto", "pid", "h", "mes", "modelo", "q10", "q50", "q90", "actual"]),
        "alertas_tenderos.csv": (alertas, ["producto", "pid", "nivel", "texto", "cambio", "mes"]),
        "vecinos.csv": ([{"producto": datos.nombres[k], "vecino": v["nombre"], "rho": round(v["rho"], 4)} for k, vs in vecinos.items() for v in vs],
                        ["producto", "vecino", "rho"]),
        "cambios_de_nivel.csv": ([{"producto": datos.nombres[k], "desde": c.fecha, "cambio": round(c.cambio, 4), "segmentos": c.segmentos,
                                   "umbral_nulo_95": round(umbrales[k], 4), "se_muestra": k in cambios}
                                  for k, c in cambios_todos.items() if c],
                                 ["producto", "desde", "cambio", "segmentos", "umbral_nulo_95", "se_muestra"]),
        "grupos_movimiento.csv": ([{"producto": datos.nombres[k], "grupo": e} for k, e in sorted(g.etiqueta.items(), key=lambda kv: kv[1])],
                                  ["producto", "grupo"]),
    }
    return {"pagina": {"pronosticos": pron, "alertas": alertas, "vecinos": vecinos, "cambios": cambios,
                       "sustitutos": sus, "modelos": modelos},
            "tablas": tablas,
            "resumen": {"origen": p.origen or None, "seleccion": p.seleccion, "pronosticos": len(p.filas), "alertas": len(alertas),
                        "grupos": {"k": g.k, "silueta": round(g.silueta, 4)}, "cambios_recientes": len(cambios),
                        "motivo_sin_pronostico": p.motivo_ausente}}


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    raiz = Path(argv[0]) if argv else Path.cwd()
    try:
        r = ejecutar(raiz)
    except CrudoAlterado as e:
        print("ERROR: " + str(e))
        return 2
    except (FileNotFoundError, RuntimeError) as e:
        print("ERROR: " + str(e))
        return 1
    v = r["validacion_estacional"]
    print()
    print(f"Mes más reciente: {r['mes']} · {r['productos_en_tablero']} productos en el tablero")
    print(f"Baratos: {r['estados']['barato']} · normales: {r['estados']['normal']} · caros: {r['estados']['caro']}")
    print(f"Consejo de temporada: acierta {v['tasa']:.1%} (línea base {v['linea_base']:.1%}, {v['evaluados']} casos) -> "
          + ("se muestra" if v["se_muestra"] else "NO se muestra"))
    print(f"Canasta: ${r['canasta']['ultimo_costo']:,.0f}".replace(",", ".") if r["canasta"]["ultimo_costo"] else "Canasta: sin meses completos")
    print(f"Página: {r['pagina']}")
    return 0
