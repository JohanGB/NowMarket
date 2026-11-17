"""Reproduce LightGBM e ingenuo en validación con el código actual y mide el efecto de elegir la lista de
entrenamiento solo con lo publicado (regla factible: ≥72 % de los meses disponibles hasta t, que equivale a 120/166)."""
import sys, json, copy, numpy as np, pandas as pd, yaml
from pathlib import Path
from mercado_al_dia.modelos import datos as md, evaluacion as ev, familias
raiz, reg = Path(sys.argv[1]), Path(sys.argv[2])
cfg = yaml.safe_load((raiz / "config/modelos.yaml").read_text(encoding="utf-8"))
d = md.cargar(raiz, cfg)
orig = ev.origenes(cfg["validacion"]["desde"], cfg["validacion"]["hasta"]); hasta = pd.Period(cfg["validacion"]["hasta"], "M")
regv = pd.read_csv(reg / "pronosticos_validacion.csv", encoding="utf-8-sig")
S = json.load(open(reg / "seleccion.json", encoding="utf-8"))
class LGBMAsOf(familias.LightGBMGlobal):
    nombre = "lightgbm_asof"
    def ajustar(self, datos, t):
        L = datos.logp.loc[:t]; n = len(L)
        datos.entrenamiento = [p for p in L.columns if L[p].notna().sum() >= 0.72 * n]
        print("   refit", t, "productos", len(datos.entrenamiento)); self.tablas.clear()
        super().ajustar(datos, t)
    def predecir(self, datos, t, prods):
        return super().predecir(datos, t, prods)
T = {"q10": .1, "q50": .5, "q90": .9}
def pin(df): return np.mean([np.where(df.y - df[c] >= 0, t * (df.y - df[c]), (t - 1) * (df.y - df[c])) for c, t in T.items()], axis=0)
claves = regv[regv.modelo == "lightgbm"][["pid", "origen", "h"]]
out = {}
for M in (familias.Ingenuo, familias.LightGBMGlobal, LGBMAsOf):
    dd = copy.copy(d)
    p = ev.rodar(M(cfg), dd, orig, d.evaluacion, int(cfg["reajuste_meses"]), hasta)
    p = p.merge(claves, on=["pid", "origen", "h"])
    out[M.nombre] = p
    if M.nombre in ("ingenuo", "lightgbm"):
        r = regv[regv.modelo == M.nombre].merge(p, on=["pid", "origen", "h"], suffixes=("_r", ""))
        print(M.nombre, "filas", len(p), "máx |dif| con el registro:", float(np.abs(r[["q10_r", "q50_r", "q90_r"]].to_numpy() - r[["q10", "q50", "q90"]].to_numpy()).max()))
for h in (1, 2, 3):
    res = {}
    for k, p in out.items():
        g = p[p.h == h].copy()
        cq = S["cqr"]["lightgbm" if k.startswith("lightgbm") else k][str(h)]
        g["q10"] -= cq; g["q90"] += cq; g["L"] = pin(g); res[k] = g.set_index(["pid", "origen"]).L
    base = res["ingenuo"]
    for k in ("lightgbm", "lightgbm_asof"):
        a = res[k]; j = a.index.intersection(base.index)
        la = a[j].groupby(level="origen").sum().values; lb = base[j].groupby(level="origen").sum().values
        rng = np.random.default_rng(int(cfg["semilla"])); idx = rng.integers(0, len(la), (2000, len(la)))
        m = 1 - la[idx].sum(1) / lb[idx].sum(1)
        print(f"h={h} {k:14} pinball={a.mean():.5f} mejora vs ingenuo={1 - la.sum() / lb.sum():+.4f} IC90 iid=[{np.quantile(m, .05):+.4f}, {np.quantile(m, .95):+.4f}]")
