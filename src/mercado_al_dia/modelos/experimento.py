"""Experimento de la fase 2: ``python -m mercado_al_dia.modelos.experimento validacion|prueba``.

``validacion`` corre todas las familias en el periodo de validación, calcula la calibración
conformal y fija la selección en ``models/registro/seleccion.json``.
``prueba`` exige esa selección (no se puede elegir mirando la prueba), corre el periodo de
prueba una sola vez, aplica la calibración de validación y reporta. Si la prueba ya se corrió
con la misma configuración y los mismos datos, se niega a repetirla (use --forzar y quedará
anotado en el registro).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

from . import evaluacion as ev
from . import familias, metricas
from .datos import cargar


def _familias(cfg: dict, con_nbeats: bool):
    fs = [c(cfg) for c in familias.LINEAS_BASE] + [familias.Sarimax(cfg), familias.LightGBMGlobal(cfg)]
    if con_nbeats:
        try:
            from .nbeats import NBeats
            import jax  # noqa: F401
            fs.append(NBeats(cfg))
        except ImportError:
            print("  (N-BEATS omitido: instale JAX con `pip install .[dl]`)")
    return fs


def correr(raiz: Path, fase: str, con_nbeats: bool = True, forzar: bool = False, decir=print) -> dict:
    raiz = Path(raiz)
    cfg = yaml.safe_load((raiz / "config" / "modelos.yaml").read_text(encoding="utf-8"))
    datos = cargar(raiz, cfg)
    reg = raiz / "models" / "registro"
    reg.mkdir(parents=True, exist_ok=True)
    huella = ev.huella(raiz, cfg)
    periodo = cfg[fase]
    orig = ev.origenes(periodo["desde"], periodo["hasta"])
    objetivo_hasta = pd.Period(cfg["validacion"]["hasta"], "M") if fase == "validacion" else datos.ultimo
    escala = metricas.escala_mase(datos.logp, pd.Period(cfg["validacion"]["desde"], "M") - 1)

    seleccion_ruta = reg / "seleccion.json"
    if fase == "prueba":
        if not seleccion_ruta.exists():
            raise RuntimeError("Primero corra la validación: la selección no puede hacerse mirando la prueba.")
        sel = json.loads(seleccion_ruta.read_text(encoding="utf-8"))
        if sel["huella"]["sha256_config"] != huella["sha256_config"] or sel["huella"]["sha256_datos"] != huella["sha256_datos"]:
            raise RuntimeError("La configuración o los datos cambiaron desde la validación: repítala antes de la prueba.")
        previa = reg / "prueba.json"
        if previa.exists() and not forzar:
            raise RuntimeError("La prueba ya se corrió con esta selección. El conjunto de prueba se usa una sola vez.")

    preds, tiempos, extra = [], {}, {}
    for m in _familias(cfg, con_nbeats):
        t0 = time.time()
        decir(f"  {fase}: {m.nombre} ...")
        p = ev.rodar(m, datos, orig, datos.evaluacion, int(cfg["reajuste_meses"]), objetivo_hasta)
        tiempos[m.nombre] = round(time.time() - t0, 1)
        if getattr(m, "fallas", None):
            extra[f"fallas_{m.nombre}"] = m.fallas[:20]
        if m.nombre == "lightgbm":
            extra["importancia_lightgbm"] = m.importancia()
        if getattr(m, "productos_por_ajuste", None):
            extra[f"productos_entrenamiento_{m.nombre}"] = m.productos_por_ajuste
        p["familia"] = m.familia
        preds.append(p)
    preds = [p for p in preds if len(p)]
    pred = pd.concat(preds, ignore_index=True)
    if fase == "prueba":
        pred = pred[pred["modelo"].isin(json.loads(seleccion_ruta.read_text(encoding="utf-8"))["cqr"])]
    bases = [c.nombre for c in familias.LINEAS_BASE]
    extra["modelos_sin_pronosticos"] = sorted(set(tiempos) - set(pred["modelo"]))
    # Comparación justa: todas las familias se miden sobre los mismos (producto, origen, horizonte).
    claves = pred[["pid", "origen", "h"]].astype(str).agg("|".join, axis=1)
    pred["clave"] = claves
    comunes = set.intersection(*(set(g["clave"]) for _, g in pred.groupby("modelo")))
    extra["casos_por_modelo"] = pred.groupby("modelo").size().to_dict()
    extra["casos_comunes"] = len(comunes)
    pred = pred[pred["clave"].isin(comunes)].drop(columns="clave")

    if fase == "validacion":
        ajustes = {m: ev.cqr(g, cfg["cobertura_objetivo"]) for m, g in pred.groupby("modelo")}
        cal = pd.concat([ev.aplicar_cqr(g, ajustes[m]) for m, g in pred.groupby("modelo")])
        tabla = ev.tabla_metricas(pred, cfg, escala)
        tabla_cal = ev.tabla_metricas(cal, cfg, escala)
        sel = ev.seleccionar(tabla_cal, cal, bases, cfg)
        salida = {"huella": huella, "seleccion": sel, "cqr": ajustes, "tiempos_s": tiempos, **extra,
                  "metricas": tabla.to_dict("records"), "metricas_calibradas": tabla_cal.to_dict("records")}
        seleccion_ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pred.to_csv(reg / "pronosticos_validacion.csv", index=False, encoding="utf-8-sig")
        return salida

    sel = json.loads(seleccion_ruta.read_text(encoding="utf-8"))
    cal = pd.concat([ev.aplicar_cqr(g, {int(k): v for k, v in sel["cqr"][m].items()}) for m, g in pred.groupby("modelo")])
    tabla_cal = ev.tabla_metricas(cal, cfg, escala)
    por_producto = []
    for (m, h, pid), g in cal.groupby(["modelo", "h", "pid"]):
        por_producto.append({"modelo": m, "h": int(h), "pid": pid, **metricas.resumen(g, cfg["cuantiles"], escala)})
    salida = {"huella": huella, "seleccion_usada": sel["seleccion"], "tiempos_s": tiempos, **extra,
              "forzada": bool(forzar), "metricas_calibradas": tabla_cal.to_dict("records"),
              "por_producto": por_producto}
    (reg / "prueba.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cal.to_csv(reg / "pronosticos_prueba.csv", index=False, encoding="utf-8-sig")
    return salida


def main(argv=None) -> int:
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="Fase 2 de NowMarket: validación y prueba de modelos.")
    p.add_argument("fase", choices=["validacion", "prueba"])
    p.add_argument("--raiz", type=Path, default=Path.cwd())
    p.add_argument("--sin-nbeats", action="store_true")
    p.add_argument("--forzar", action="store_true", help="repetir la prueba (queda anotado)")
    a = p.parse_args(argv)
    r = correr(a.raiz, a.fase, not a.sin_nbeats, a.forzar)
    clave = "metricas_calibradas"
    print(pd.DataFrame(r[clave])[["modelo", "h", "pinball", "mae_pct", "mase", "cobertura", "ancho_pct", "acierto_direccion"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    if a.fase == "validacion":
        for h, s in r["seleccion"].items():
            print(f"h={h}: se despliega {s['modelo']} (menor pérdida: {s['mejor_modelo']}; "
                  f"mejor línea base: {s['mejor_linea_base']}; bloque {s['bloque']})")
            for c in s["candidatos"]:
                sens = "  ".join(f"b={x['bloque']} [{x['ic90'][0]:+.1%}, {x['ic90'][1]:+.1%}]"
                                 for x in c.get("sensibilidad_descriptiva", []))
                print(f"     {c['modelo']:9} mejora {c['mejora']:+.1%}  IC90 [{c['ic90'][0]:+.1%}, {c['ic90'][1]:+.1%}]"
                      + ("  significativa" if c["significativa"] else "") + (f"   (sensibilidad: {sens})" if sens else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
