"""Reimplementación independiente (solo numpy/pandas; no importa mercado_al_dia)."""
import sys, json, math, numpy as np, pandas as pd
reg = sys.argv[1]
TAU = {"q10": 0.1, "q50": 0.5, "q90": 0.9}
def pin(y, q, t):  # pérdida de cuantiles (pinball)
    u = y - q; return np.where(u >= 0, t * u, (t - 1) * u)
def metr(g):
    y = g.y.values
    L = np.mean([pin(y, g[c].values, t) for c, t in TAU.items()], axis=0)
    return pd.Series({"n": len(g), "pinball": L.mean(), "cobertura": np.mean((y >= g.q10) & (y <= g.q90)),
                      "error_tipico": np.mean(np.abs(np.exp(y) - np.exp(g.q50)) / np.exp(y)),
                      "ancho": np.mean(np.exp(g.q90 - g.q10) - 1)})
pr = pd.read_csv(f"{reg}/pronosticos_prueba.csv", encoding="utf-8-sig")
va = pd.read_csv(f"{reg}/pronosticos_validacion.csv", encoding="utf-8-sig")
P = json.load(open(f"{reg}/prueba.json", encoding="utf-8")); S = json.load(open(f"{reg}/seleccion.json", encoding="utf-8"))
mi = pr.groupby(["modelo", "h"]).apply(metr, include_groups=False).reset_index()
pub = pd.DataFrame(P["metricas_calibradas"])[["modelo", "h", "pinball", "cobertura", "mae_pct", "ancho_pct"]]
c = mi.merge(pub, on=["modelo", "h"], suffixes=("", "_pub"))
c["dif_pinball"] = c.pinball - c.pinball_pub; c["dif_cob"] = c.cobertura - c.cobertura_pub; c["dif_err"] = c.error_tipico - c.mae_pct
pd.set_option("display.width", 250); print(c.round(5).to_string(index=False))
print("máx |dif|:", float(c[["dif_pinball", "dif_cob", "dif_err"]].abs().max().max()))
# Casos comunes por modelo
print("casos por modelo (prueba):", pr.groupby(["modelo"]).size().to_dict(), "| claves comunes:", pr.drop_duplicates(["pid", "origen", "h"]).shape[0])
print("casos por modelo (validación):", va.groupby(["modelo"]).size().to_dict())
# Rangos de fechas
print("prueba: orígenes", pr.origen.min(), pr.origen.max(), "objetivos", pr.objetivo.min(), pr.objetivo.max())
print("validación: orígenes", va.origen.min(), va.origen.max(), "objetivos", va.objetivo.min(), va.objetivo.max())
# CQR independiente sobre la validación sin calibrar
print("\nCQR recalculado vs registrado:")
for m, g in va.groupby("modelo"):
    for h, gh in g.groupby("h"):
        e = np.sort(np.maximum(gh.q10 - gh.y, gh.y - gh.q90).values); n = len(e)
        k = min(n, math.ceil((n + 1) * 0.8)); a = e[k - 1]
        print(f"  {m:20} h={h} n={n} ajuste={a:.6f} registrado={S['cqr'][m][str(h)]:.6f} {'OK' if abs(a - S['cqr'][m][str(h)]) < 1e-12 else 'DIFIERE'}")
# Validación calibrada: pinball por modelo/h y mejora vs ingenuo
vc = va.copy(); vc["a"] = [S["cqr"][m][str(h)] for m, h in zip(vc.modelo, vc.h)]; vc["q10"] -= vc.a; vc["q90"] += vc.a
mv = vc.groupby(["modelo", "h"]).apply(metr, include_groups=False).reset_index()
print("\nValidación calibrada:"); print(mv.pivot(index="modelo", columns="h", values="pinball").round(5))
print(mv.pivot(index="modelo", columns="h", values="cobertura").round(3))
vc.to_pickle(sys.argv[2])
# Mejora LightGBM vs ingenuo en prueba (docs: 4,8 % a 1 mes; 5,1 % y 9,1 % a 2 y 3)
for h in (1, 2, 3):
    a = mi[(mi.modelo == "lightgbm") & (mi.h == h)].pinball.iloc[0]; b = mi[(mi.modelo == "ingenuo") & (mi.h == h)].pinball.iloc[0]
    print(f"prueba h={h}: mejora lightgbm vs ingenuo = {1 - a / b:.4f}")
