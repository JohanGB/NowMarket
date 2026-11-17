import sys, datetime as dt, re, pandas as pd, numpy as np, openpyxl, unicodedata
proc = pd.read_csv(sys.argv[1], encoding="utf-8-sig", dtype={"hoja": str})
crudo = pd.read_pickle(sys.argv[2]); raw = sys.argv[3]
c = crudo.set_index(["archivo", "hoja", "fila"])
rng = np.random.default_rng(20261117)
m = proc.iloc[np.sort(rng.choice(len(proc), 30, replace=False))]
def mes(v):
    s = str(v)
    if re.match(r"\d{4}-\d{2}", s): return s[:7]
    return "?" + s
dif = []
print("| # | fecha | producto (procesado) | mercado | precio CSV | celda | fecha cruda | producto crudo | precio crudo | ¿coincide? |")
for k, (_, r) in enumerate(m.iterrows(), 1):
    x = c.loc[(r.archivo, str(r.hoja), int(r.fila))]
    pc = float(str(x.precio_crudo).replace(",", ".")) if x.precio_crudo not in ("None",) else None
    ok = {"fecha": mes(x.fecha_cruda) == r.fecha, "producto": " ".join(str(x.producto).split()) == r.producto_original,
          "mercado": " ".join(str(x.mercado).split()) == r.mercado, "precio": pc is not None and abs(pc - r.precio) < 1e-9}
    bad = [k2 for k2, v in ok.items() if not v]
    if bad: dif.append((k, bad))
    print(f"| {k} | {r.fecha} | {r.producto} | {r.mercado.replace('Bogotá, D.C., ', '')} | {r.precio:g} | `{r.archivo.split('/')[-1]}#{r.hoja}!{r.fila}` | {str(x.fecha_cruda)[:10]} | {x.producto} | {x.precio_crudo} | {'sí' if not bad else 'NO: ' + ','.join(bad)} |")
print("diferencias:", dif)
# Celda exacta con openpyxl NO read-only para 5 de ellas (confirmar que la fila Excel es la fila real)
for _, r in m.head(5).iterrows():
    wb = openpyxl.load_workbook(raw + "/" + r.archivo, read_only=True, data_only=True)
    ws = wb[str(r.hoja)]
    fila = next(ws.iter_rows(min_row=int(r.fila), max_row=int(r.fila), values_only=True))
    print(r.archivo.split("/")[-1], r.hoja, r.fila, [v for v in fila if v is not None]); wb.close()
