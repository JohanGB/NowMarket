"""Reimplementación independiente del consejo «suele subir/bajar» (ficha consejo_estacional.md y D-015).
No importa mercado_al_dia. Variantes para los detalles que la ficha no fija."""
import sys, math, itertools, numpy as np, pandas as pd
proc = pd.read_csv(sys.argv[1], encoding="utf-8-sig", dtype={"hoja": str})
pub = pd.read_csv(sys.argv[2], encoding="utf-8-sig")
c = proc[proc.mercado.str.contains("Corabastos")]
W = np.log(c.pivot(index="fecha", columns="producto_id", values="precio"))
W.index = pd.PeriodIndex(W.index, freq="M"); W = W.reindex(pd.period_range(W.index.min(), W.index.max(), freq="M"))
X = W.to_numpy(); per = W.index; mes = np.array([p.month - 1 for p in per])
wts = np.array([.5] + [1] * 11 + [.5]) / 12
def tendencia(x):
    out = np.full_like(x, np.nan)
    for i in range(6, len(x) - 6):
        v = x[i - 6:i + 7]
        if not np.isnan(v).any(): out[i] = v @ wts
    return out
def correr(umbral_log, min_anios, ddof, desde="2018-01", hasta="2026-09"):
    i0, i1 = per.get_loc(pd.Period(desde, "M")), per.get_loc(pd.Period(hasta, "M"))
    casos = []
    for j, pid in enumerate(W.columns):
        x_full = X[:, j]
        for t in range(i0, i1 + 1):
            x = x_full[:t + 1]
            if np.isnan(x[t]) or np.isnan(x_full[t + 1]): continue
            r = x - tendencia(x)
            m0, m1 = mes[t], (mes[t] + 1) % 12
            rs = [r[(mes[:t + 1] == m) & ~np.isnan(r)] for m in range(12)]
            if min(len(v) for v in rs) < min_anios: continue
            ef = np.array([v.mean() for v in rs]); ef -= ef.mean()
            se = [v.std(ddof=ddof) / math.sqrt(len(v)) for v in rs]
            cambio = ef[m1] - ef[m0]; e = math.hypot(se[m0], se[m1])
            umbral = math.log(1.03) if umbral_log else None
            grande = abs(cambio) >= umbral if umbral_log else abs(math.exp(cambio) - 1) >= 0.03
            if not (grande and abs(cambio) > 2 * e): continue
            real = np.sign(x_full[t + 1] - x[t])
            base = np.sign(x[t - 11] - x[t - 12]) if t >= 12 and not np.isnan(x[t - 11]) and not np.isnan(x[t - 12]) else np.nan
            casos.append((pid, str(per[t]), np.sign(cambio), real, base))
    return pd.DataFrame(casos, columns=["pid", "origen", "pred", "real", "base"])
for umbral_log, min_anios, ddof in itertools.product([False], [5], [1]):
    d = correr(umbral_log, min_anios, ddof)
    ac = (d.pred == d.real).mean(); bm = d.base.notna()
    print(f"umbral_log={umbral_log} min_anios={min_anios} ddof={ddof}: casos={len(d)} productos={d.pid.nunique()} acierto={ac:.4f} "
          f"| base (mismos casos, sin base=fallo)={(d.base == d.real).mean():.4f} | base solo casos con base={(d.base[bm] == d.real[bm]).mean():.4f} (n={bm.sum()})")
    if (not umbral_log) and ddof == 1: keep = d
k = keep.groupby("pid").apply(lambda g: pd.Series({"ev": len(g), "ac": int((g.pred == g.real).sum())}), include_groups=False).reset_index()
m = pub.merge(k, left_on="producto_id", right_on="pid", how="outer")
print("productos publicados:", len(pub), "evaluados publicados:", int(pub.evaluados.sum()), "aciertos:", int(pub.aciertos.sum()), "=", round(pub.aciertos.sum() / pub.evaluados.sum(), 4))
print("productos con distinto nº de casos:", int((m.evaluados != m.ev).sum()), "| con distinto nº de aciertos:", int((m.aciertos != m.ac).sum()))
print(m[(m.evaluados != m.ev) | (m.aciertos != m.ac)].head(15).to_string(index=False))
# Corte temporal: ¿cuánto del 78,2 % cae en la ventana de prueba de modelos?
keep["per"] = pd.PeriodIndex(keep.origen, freq="M")
for a, b in [("2018-01", "2021-10"), ("2021-11", "2023-10"), ("2023-11", "2026-09")]:
    s = keep[(keep.per >= pd.Period(a, "M")) & (keep.per <= pd.Period(b, "M"))]
    print(f"  {a}..{b}: casos={len(s)} acierto={(s.pred == s.real).mean():.4f} base={(s.base == s.real).mean():.4f}")
# Bootstrap por mes de origen (casos del mismo mes no son independientes)
g = keep.assign(a=(keep.pred == keep.real).astype(int), b=(keep.base == keep.real).astype(int)).groupby("origen")[["a", "b"]].agg(["sum", "count"])
A, N, B = g[("a", "sum")].values, g[("a", "count")].values, g[("b", "sum")].values
rng = np.random.default_rng(7); idx = rng.integers(0, len(A), (20000, len(A)))
acc = A[idx].sum(1) / N[idx].sum(1); dif = (A[idx].sum(1) - B[idx].sum(1)) / N[idx].sum(1)
print("IC95 % acierto (bootstrap de meses):", np.quantile(acc, [.025, .975]).round(4), "| IC95 % ventaja sobre la base:", np.quantile(dif, [.025, .975]).round(4))
