"""Pruebas de mutación: aplica cada error a la copia, corre tests/ (y la prueba de auditoría) y restaura."""
import subprocess, sys, os, re, json
from pathlib import Path
R = Path(sys.argv[1]); SRC = R / "src/mercado_al_dia"
M = [
 ("M1", "Fuga de un mes en el entrenamiento de LightGBM (objetivos hasta t+1)", "modelos/familias.py",
  'ok = (t["mes"] + h <= hasta) & t["y"].notna()', 'ok = (t["mes"] + h <= hasta + 1) & t["y"].notna()'),
 ("M2", "Media de 12 meses centrada (usa 6 meses futuros) en la variable dev12", "modelos/familias.py",
  '"dev12": L - L.rolling(12, min_periods=8).mean(),', '"dev12": L - L.rolling(12, min_periods=8, center=True).mean(),'),
 ("M3", "ONI sin el rezago de publicación (temporada que termina en t+1)", "modelos/familias.py",
  'largo["oni"] = oni.reindex(meses - int(ex["oni_rezago"])).to_numpy()', 'largo["oni"] = oni.reindex(meses - int(ex["oni_rezago"]) + 2).to_numpy()'),
 ("M4", "Abastecimiento del mes t+1 (aún no publicado)", "modelos/familias.py",
  'a.reindex(meses - ra).to_numpy() - a', 'a.reindex(meses - ra + 2).to_numpy() - a'),
 ("M5", "SARIMAX estimado con toda la serie (incluye el futuro)", "modelos/familias.py",
  'y = datos.logp.loc[:hasta, pid]', 'y = datos.logp.loc[:, pid]'),
 ("M6", "Calibración conformal (CQR) recalculada con los datos de la prueba", "modelos/experimento.py",
  'cal = pd.concat([ev.aplicar_cqr(g, {int(k): v for k, v in sel["cqr"][m].items()}) for m, g in pred.groupby("modelo")])',
  'cal = pd.concat([ev.aplicar_cqr(g, ev.cqr(g, cfg["cobertura_objetivo"])) for m, g in pred.groupby("modelo")])'),
 ("M7", "Bootstrap de casos (producto × origen) en lugar de orígenes completos", "modelos/metricas.py",
  'por_origen = m.groupby("origen")[["la", "lb"]].sum()', 'por_origen = m.groupby(["origen", "pid"])[["la", "lb"]].sum()'),
 ("M8", "La validación conserva objetivos que caen en la ventana de prueba", "modelos/experimento.py",
  'objetivo_hasta = pd.Period(cfg["validacion"]["hasta"], "M") if fase == "validacion" else datos.ultimo',
  'objetivo_hasta = datos.ultimo'),
]
env = dict(os.environ, PYTHONPATH=str(R / "src"), MAD_RAIZ=str(R), PYTHONIOENCODING="utf-8")
def pytest(args):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args], cwd=R, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    fall = sorted(set(re.findall(r"^FAILED (\S+)", r.stdout, re.M)))
    return [f for f in fall if "cambio_de_nivel" not in f and "umbral_nulo" not in f], r.stdout.strip().splitlines()[-1]
res = []
SOLO = sys.argv[3].split(',') if len(sys.argv) > 3 else None
for mid, desc, rel, viejo, nuevo in M:
    if SOLO and mid not in SOLO: continue
    f = SRC / rel; crudo = f.read_bytes(); txt = crudo.decode("utf-8")
    assert txt.count(viejo) == 1, (mid, txt.count(viejo))
    f.write_bytes(txt.replace(viejo, nuevo).encode("utf-8"))
    try:
        fall, resumen = pytest(["tests"])
        aud = None
        if mid in ("M1", "M2", "M3", "M4", "M5"):
            fa, _ = pytest(["docs/auditoria_independiente/test_auditoria_publicacion.py", "-k", "identico and 2023-11"])
            aud = fa
    finally:
        f.write_bytes(crudo)
    print(mid, "| detectado por tests/:", bool(fall), "|", resumen, "|", fall, "| prueba de auditoría:", aud, flush=True)
    res.append(dict(id=mid, desc=desc, archivo=rel, viejo=viejo, nuevo=nuevo, fallan=fall, resumen=resumen, auditoria=aud))
json.dump(res, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
