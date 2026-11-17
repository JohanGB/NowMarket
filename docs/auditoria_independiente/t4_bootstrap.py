"""Bootstrap independiente de orígenes: iid, bloques móviles (como el repo) y bloques circulares.
Uso: t4_bootstrap.py <pronosticos_validacion_calibrados.pkl | pronosticos_prueba.csv>"""
import sys, math, numpy as np, pandas as pd
src = sys.argv[1]
d = pd.read_pickle(src) if src.endswith(".pkl") else pd.read_csv(src, encoding="utf-8-sig")
T = {"q10": .1, "q50": .5, "q90": .9}
def pin(y, q, t): u = y - q; return np.where(u >= 0, t * u, (t - 1) * u)
d["L"] = np.mean([pin(d.y.values, d[c].values, t) for c, t in T.items()], axis=0)
def ic(la, lb, b, R=20000, seed=1, circular=False):
    n = len(la); rng = np.random.default_rng(seed); k = math.ceil(n / b)
    if b == 1: idx = rng.integers(0, n, (R, n))
    elif circular: idx = ((rng.integers(0, n, (R, k))[:, :, None] + np.arange(b)) % n).reshape(R, -1)[:, :n]
    else: idx = (rng.integers(0, n - b + 1, (R, k))[:, :, None] + np.arange(b)).reshape(R, -1)[:, :n]
    m = 1 - la[idx].sum(1) / lb[idx].sum(1)
    return np.quantile(m, [.05, .95])
for h in (1, 2, 3):
    for cand in ("lightgbm", "sarimax"):
        a = d[(d.modelo == cand) & (d.h == h)].set_index(["pid", "origen"]).L
        b = d[(d.modelo == "ingenuo") & (d.h == h)].set_index(["pid", "origen"]).L
        j = a.index.intersection(b.index)
        pa, pb = a[j].groupby(level="origen").sum().sort_index(), b[j].groupby(level="origen").sum().sort_index()
        la, lb = pa.values, pb.values; n = len(la)
        dd = la - lb; r1 = np.corrcoef(dd[:-1], dd[1:])[0, 1]
        # Diebold-Mariano con Newey-West (rezagos h-1 y h) sobre la diferencia por origen
        def dm(L):
            x = dd - dd.mean(); g0 = (x @ x) / n
            s = g0 + 2 * sum((1 - l / (L + 1)) * (x[l:] @ x[:-l]) / n for l in range(1, L + 1))
            return dd.mean() / math.sqrt(s / n)
        txt = f"h={h} {cand:8} orígenes={n} mejora={1 - la.sum() / lb.sum():+.4f} rho1={r1:+.2f} | iid {ic(la, lb, 1).round(4)}"
        for bl in (2, 3, 6):
            txt += f" | móvil b={bl} {ic(la, lb, bl).round(4)} circ {ic(la, lb, bl, circular=True).round(4)}"
        txt += f" | DM t(NW L=h)={dm(h):+.2f}"
        print(txt)
