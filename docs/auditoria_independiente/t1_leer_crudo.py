"""Lector independiente (no importa mercado_al_dia). Vuelca TODAS las filas de datos de los Excel
mensuales a un parquet/CSV con archivo, hoja, fila y valores crudos, más las notas al pie."""
import sys, glob, os, datetime as dt, unicodedata, re, json
import openpyxl, pandas as pd
raw = sys.argv[1]; out = sys.argv[2]
def plano(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())
filas, notas = [], []
for ruta in sorted(glob.glob(raw + "/sipsa/precios_mensual/*.xlsx")):
    rel = os.path.relpath(ruta, raw).replace("\\", "/")
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    for ws in wb.worksheets:
        enc = None
        for i, f in enumerate(ws.iter_rows(values_only=True), 1):
            if enc is None:
                if i > 30: break
                if f and any(plano(v) == "fecha" for v in f):
                    enc = {plano(v): j for j, v in enumerate(f) if v is not None}
                    cp = [j for k, j in enc.items() if k.startswith("precio")]
                    assert len(cp) == 1, (rel, ws.title, enc)
                    cm = enc.get("mercado", enc.get("fuente"))
                continue
            if not f or all(v is None for v in f): continue
            g = lambda j: f[j] if j is not None and j < len(f) else None
            fe, pr = g(enc["fecha"]), g(enc["producto"])
            if pr is None:
                txt = " ".join(str(v) for v in f if v is not None)
                if "$" in txt or "unidad" in txt.lower() or "litro" in txt.lower(): notas.append((rel, ws.title, i, txt[:300]))
                continue
            filas.append(dict(archivo=rel, hoja=ws.title, fila=i, fecha_cruda=fe, grupo=g(enc.get("grupo")),
                              producto=pr, mercado=g(cm), precio_crudo=g(cp[0])))
    wb.close()
d = pd.DataFrame(filas)
d["fecha_cruda"] = d["fecha_cruda"].astype(str); d["precio_crudo"] = d["precio_crudo"].astype(str)
d.to_pickle(out)
print(len(d), "filas crudas"); print(json.dumps(sorted(set(n[3] for n in notas)), ensure_ascii=False, indent=0)[:4000])
