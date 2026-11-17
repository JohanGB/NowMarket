import sys, pandas as pd, numpy as np
proc = pd.read_csv(sys.argv[1], encoding="utf-8-sig", dtype={"hoja": str})
c = proc[proc.mercado.str.contains("Corabastos")]
w = c.pivot(index="fecha", columns="producto_id", values="precio").sort_index()
r = np.log(w).diff()
r.index = pd.PeriodIndex(r.index, freq="M")
ene = r[r.index.month == 1].abs(); otros = r[r.index.month != 1].abs()
print("mediana |cambio log| en enero (cambio de archivo):", round(float(np.nanmedian(ene.values)), 4), "otros meses:", round(float(np.nanmedian(otros.values)), 4))
print("Por año, fracción de productos con |cambio| > log(1.5) en enero vs. promedio otros meses:")
for y in range(2014, 2027):
    e = r.loc[str(y) + "-01"].abs(); o = r.loc[str(y)][r.loc[str(y)].index.month != 1].abs()
    print(y, round(float((e > np.log(1.5)).mean()), 3), round(float((o > np.log(1.5)).mean().mean()), 3))
print()
u = proc[proc.unidad != "kg"].producto_id.unique()
print("productos con unidad != kg:", sorted(u))
sosp = [p for p in proc.producto_id.unique() if any(k in p for k in ["litro", "ml", "lata", "botella", "sobre", "paquete", "unidad", "doy pack", "frasco", "bolsa", "caja"])]
print("nombres con presentación (quedan en $/kg):", sorted(set(sosp) - set(u)))
for pid in ["huevo rojo a", "huevo blanco a", "aceite vegetal mezcla", "aceite girasol", "bocadillo veleno"]:
    if pid in w: print(pid, w[pid].loc["2017-10":"2019-03"].round(0).to_dict())
