import sys, re, json, unicodedata, collections, pandas as pd, numpy as np
proc = pd.read_csv(sys.argv[1], encoding="utf-8-sig", dtype={"hoja": str}); crudo = pd.read_pickle(sys.argv[2])
cal = json.load(open(sys.argv[3], encoding="utf-8"))
def plano(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())
b = crudo[crudo["mercado"].map(plano).str.startswith("bogota d c")].copy()
b["mes"] = b["fecha_cruda"].str[:7]
print("filas crudas Bogotá:", len(b), "| meses ilegibles:", (~b.mes.str.match(r"\d{4}-\d{2}")).sum())
b["precio"] = pd.to_numeric(b["precio_crudo"], errors="coerce")
print("precio no numérico o <=0:", (~(b.precio > 0)).sum(), b.loc[~(b.precio > 0), "precio_crudo"].value_counts().head().to_dict())
b = b[b.precio > 0]
b["m"], b["p"] = b.mercado.map(plano), b.producto.map(plano)
eq = {"ciruela negra chilena": "ciruela importada", "ciruela negra importada": "ciruela importada", "galletas saladas 3 tacos": "galletas saladas"}
b["p2"] = b.p.replace(eq)
g = b.groupby(["mes", "m", "p2"])
n = g.size(); nval = g.precio.nunique()
print("claves:", len(n), "| con duplicado:", (n > 1).sum(), "| duplicados idénticos (filas sobrantes):", int((n[nval == 1] - 1).sum()),
      "| claves en conflicto:", int(((n > 1) & (nval > 1)).sum()))
print("calidad.json: idénticos", cal["duplicados_identicos"], "conflicto", len(cal["duplicados_en_conflicto"]))
esperado = b[b.set_index(["mes", "m", "p2"]).index.isin(nval[nval == 1].index)].drop_duplicates(["mes", "m", "p2"])
proc["m"] = proc.mercado.map(plano)
k1 = set(zip(esperado.mes, esperado.m, esperado.p2)); k2 = set(zip(proc.fecha, proc.m, proc.producto_id))
print("claves esperadas", len(k1), "en CSV", len(k2), "faltan en CSV", len(k1 - k2), "sobran en CSV", len(k2 - k1))
mm = esperado.merge(proc, left_on=["mes", "m", "p2"], right_on=["fecha", "m", "producto_id"], suffixes=("_c", "_p"))
print("precios distintos:", int((np.abs(mm.precio_c - mm.precio_p) > 1e-9).sum()), "de", len(mm))
# Conflictos: muestra
for d in cal["duplicados_en_conflicto"][:10]: print("  conflicto:", d["fecha"], d["mercado"], d["producto"], d["precios"], d["origenes"])
# ¿Conflictos en Corabastos y en productos de la canasta?
cor = [d for d in cal["duplicados_en_conflicto"] if "Corabastos" in d["mercado"]]
print("conflictos en Corabastos:", len(cor), [ (d["fecha"], d["producto"]) for d in cor][:20])
# Renombres: reglas D-013 en Corabastos
c = b[b.m == "bogota d c corabastos"]
for desde, hacia in eq.items():
    a = sorted(c[c.p == desde].mes.unique()); z = sorted(c[c.p == hacia].mes.unique())
    ga = c[c.p == desde].grupo.unique(); gz = c[c.p == hacia].grupo.unique()
    print(f"renombre {desde!r}->{hacia!r}: {a[0] if a else None}..{a[-1] if a else None} ({len(a)} meses) | destino {z[0]}..{z[-1]} ({len(z)}) | solapan {len(set(a)&set(z))} | grupos {ga} {gz}")
print("equivalencias aplicadas (calidad.json):", cal["equivalencias_aplicadas"])
# Saltos ×3
p = proc.sort_values("fecha").copy(); p["per"] = pd.PeriodIndex(p.fecha, freq="M")
saltos = []
for (m_, pid), s in p.groupby(["m", "producto_id"]):
    s = s.sort_values("per"); r = s.precio.to_numpy(); per = s.per.to_numpy()
    for i in range(1, len(s)):
        if (per[i] - per[i - 1]).n == 1 and (r[i] / r[i - 1] >= 3 or r[i] / r[i - 1] <= 1 / 3): saltos.append((m_, pid, str(per[i]), r[i - 1], r[i]))
print("saltos x3 recalculados:", len(saltos), "| calidad.json:", len(cal["saltos_extremos"]))
for x in saltos: print("  ", x)
# Saltos tras huecos (no los revisa el código)
hue = []
for (m_, pid), s in p.groupby(["m", "producto_id"]):
    s = s.sort_values("per"); r = s.precio.to_numpy(); per = s.per.to_numpy()
    for i in range(1, len(s)):
        if (per[i] - per[i - 1]).n > 1 and (r[i] / r[i - 1] >= 3 or r[i] / r[i - 1] <= 1 / 3): hue.append((m_, pid, str(per[i-1]), str(per[i]), r[i - 1], r[i]))
print("saltos x3 a través de un hueco (no reportados):", len(hue)); [print("  ", x) for x in hue[:15]]
