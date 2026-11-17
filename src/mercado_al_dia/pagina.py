"""Página web estática de Mercado al Día (un solo archivo, sin librerías externas obligatorias).

Diseño: primero para celular, una pregunta por vista, máximo tres gráficas por vista.
Vistas: Este mes (barato o caro) · Un producto (historia, pronóstico y temporada) ·
Canasta (costo, pronóstico y ajuste a un presupuesto) · Tenderos (alertas del próximo mes).

Se escriben dos archivos con el mismo contenido:
- ``mercado.html``: documento completo para abrir en el computador.
- ``mercado_publicar.html``: el mismo cuerpo sin envoltura, para publicarlo como página.
Cada precio mostrado lleva su origen (archivo, hoja y fila del Excel del DANE).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import __version__
from .analisis import MESES, Canasta, Indicador, Perfil, Serie, Validacion


def _serie_compacta(s: Serie | None) -> dict | None:
    if not s:
        return None
    ini, fin = min(s), max(s)
    return {"ini": ini, "v": [round(s[i]) if i in s else None for i in range(ini, fin + 1)]}


def _perfil(p: Perfil | None) -> dict | None:
    if p is None:
        return None
    return {"efecto": [round(x, 4) for x in p.efecto], "error": [round(x, 4) for x in p.error], "anios": p.anios}


def construir(destino: Path, *, indicadores: list[Indicador], referencia: dict[str, Serie],
              comparacion: dict[str, dict[str, Serie]], perfiles: dict[str, Perfil | None],
              validacion: Validacion, mostrar_consejo: bool, canasta: Canasta, rotulo: str,
              cfg_validacion: dict, pronosticos: dict | None = None, alertas: list[dict] | None = None,
              vecinos: dict | None = None, cambios: dict | None = None, sustitutos: list[list[str]] | None = None,
              modelos: dict | None = None, generado: dt.datetime | None = None) -> Path:
    generado = generado or dt.datetime.now().astimezone()
    lo, hi = validacion.intervalo()
    pronosticos, vecinos, cambios = pronosticos or {}, vecinos or {}, cambios or {}
    productos = []
    for i in indicadores:
        productos.append({
            "id": i.producto_id, "nombre": i.producto, "grupo": i.grupo.capitalize(), "unidad": i.unidad,
            "precio": round(i.precio), "mediana": round(i.mediana_12m) if i.mediana_12m else None,
            "var12": i.variacion_12m, "anual": i.variacion_anual, "estado": i.estado,
            "consejo": i.consejo if mostrar_consejo else 0, "cambio": i.cambio_esperado, "origen": i.origen,
            "serie": _serie_compacta(referencia.get(i.producto_id)),
            "comp": {n: _serie_compacta(s.get(i.producto_id)) for n, s in comparacion.items() if s.get(i.producto_id)},
            "perfil": _perfil(perfiles.get(i.producto_id)),
            "pron": pronosticos.get(i.producto_id), "vecinos": vecinos.get(i.producto_id, []),
            "nivel": cambios.get(i.producto_id),
        })
    ids = {p["id"] for p in productos}
    from .sipsa.lector import plano
    grupos_sus = [[plano(n) for n in g if plano(n) in ids] for g in (sustitutos or [])]
    ultimo = max(canasta.costo) if canasta.costo else None
    precio_ultimo = {c["producto_id"]: referencia[c["producto_id"]].get(ultimo) for c in canasta.componentes} if ultimo else {}
    origen = {p["id"]: p["origen"] for p in productos}
    datos = {
        "version": __version__, "generado": generado.isoformat(timespec="minutes"),
        "mes": indicadores[0].mes if indicadores else "", "rotulo": rotulo, "meses": MESES,
        "productos": productos, "sustitutos": [g for g in grupos_sus if len(g) > 1],
        "alertas": alertas or [], "modelos": modelos or {},
        "validacion": {"tasa": validacion.tasa, "lo": lo, "hi": hi, "n": validacion.evaluados,
                       "base": validacion.tasa_base, "productos": validacion.productos,
                       "desde": validacion.desde, "hasta": validacion.hasta, "mostrar": mostrar_consejo,
                       "minimo": cfg_validacion.get("aciertos_minimos", 0.55)},
        "canasta": {"nombre": canasta.nombre, "costo": _serie_compacta(canasta.costo),
                    "componentes": [{**c, "precio": precio_ultimo.get(c["producto_id"]),
                                     "origen": origen.get(c["producto_id"], "")} for c in canasta.componentes],
                    "no_encontrados": canasta.no_encontrados, "faltantes": canasta.faltantes},
    }
    cuerpo = CUERPO.replace("/*DATOS*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n'
        + cuerpo + "\n</body>\n</html>\n", encoding="utf-8")
    (destino.parent / "mercado_publicar.html").write_text(cuerpo, encoding="utf-8")
    return destino


CUERPO = r"""<title>NowMarket</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=Source+Sans+3:wght@400;600&display=swap">
<style>
/* Diseño: tablero de plaza de mercado. Columna única en celular; pizarra de precios con cifras tabulares. */
:root{
  --fondo:#f2f4f1; --papel:#ffffff; --tinta:#18201b; --suave:#5d6760; --linea:#dde3dc;
  --acento:#155e63; --acento-suave:#d6ebe9; --barato:#2c7a3f; --caro:#b3261e; --banda:#e6ece5; --comp:#8b928a;
  --f-titulo:"Archivo","Arial Narrow",system-ui,sans-serif; --f-texto:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --fondo:#121614; --papel:#1b201d; --tinta:#e8ece8; --suave:#a3ada5; --linea:#2f3732;
  --acento:#5fb7b4; --acento-suave:#1f3a39; --barato:#6cc382; --caro:#f08a80; --banda:#232a26; --comp:#7d857e; color-scheme:dark}}
:root[data-theme="dark"]{
  --fondo:#121614; --papel:#1b201d; --tinta:#e8ece8; --suave:#a3ada5; --linea:#2f3732;
  --acento:#5fb7b4; --acento-suave:#1f3a39; --barato:#6cc382; --caro:#f08a80; --banda:#232a26; --comp:#7d857e; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--tinta);font:16px/1.5 var(--f-texto)}
main{max-width:760px;margin:0 auto;padding-block:16px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
header .lugar{margin:0;color:var(--suave);font-size:.85rem;letter-spacing:.04em;text-transform:uppercase}
h1{font-family:var(--f-titulo);font-weight:800;font-size:1.9rem;letter-spacing:-.01em;margin:.1rem 0 0;text-wrap:balance}
header .sub{margin:.2rem 0 0;color:var(--suave)}
nav{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:16px 0 4px;padding:6px 0;position:sticky;top:env(safe-area-inset-top,0px);background:var(--fondo);z-index:2}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);background:var(--fondo);z-index:10}
nav a{border:1px solid var(--linea);background:var(--papel);color:var(--tinta);border-radius:999px;padding:7px 4px;text-decoration:none;font-weight:600;font-size:.88rem;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
nav a[aria-current="page"]{background:var(--acento);border-color:var(--acento);color:var(--papel)}
nav a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--acento);outline-offset:2px}
section{display:none}section.activa{display:block}
.bloque{background:var(--papel);border:1px solid var(--linea);border-radius:12px;padding:14px 16px;margin:12px 0;min-width:0}
h2{font-family:var(--f-titulo);font-weight:700;font-size:1.25rem;margin:.1rem 0 .4rem;text-wrap:balance}
h3{font-family:var(--f-titulo);font-weight:700;font-size:1rem;margin:.1rem 0 .5rem}
.cifra-grande{font-family:var(--f-titulo);font-weight:800;font-size:2.1rem;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.nota{color:var(--suave);font-size:.87rem;max-width:65ch}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chips button{border:1px solid var(--linea);background:var(--papel);color:var(--tinta);border-radius:999px;padding:4px 11px;font:inherit;font-size:.84rem;cursor:pointer}
.chips button[aria-pressed="true"]{border-color:var(--acento);background:var(--acento-suave);font-weight:600}
ul.pizarra{list-style:none;margin:0;padding:0}
ul.pizarra li{display:grid;grid-template-columns:1fr auto;gap:10px;padding:9px 0;border-top:1px solid var(--linea);cursor:pointer;align-items:center}
ul.pizarra li:first-child{border-top:0}
ul.pizarra li:hover .nom{color:var(--acento)}
.nom{font-weight:600}.sub{color:var(--suave);font-size:.84rem}
.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:600}
.barato{color:var(--barato)}.caro{color:var(--caro)}
.pill{display:inline-block;align-self:start;white-space:nowrap;border-radius:999px;padding:1px 9px;font-size:.78rem;font-weight:600;border:1px solid currentColor;margin-top:2px}
input,select{font:inherit;width:100%;padding:9px 10px;border:1px solid var(--linea);border-radius:10px;background:var(--papel);color:var(--tinta)}
label{display:block;color:var(--suave);font-size:.85rem;margin-bottom:4px}
svg{display:block;width:100%;height:auto}svg text{fill:var(--suave);font:10.5px var(--f-texto)}
.leyenda{display:flex;gap:14px;flex-wrap:wrap;font-size:.82rem;color:var(--suave);margin-top:6px}
.leyenda i{display:inline-block;width:16px;height:3px;vertical-align:middle;margin-right:5px;background:var(--acento)}
.leyenda i.comp{background:var(--comp)}.leyenda i.banda{height:9px;background:var(--acento-suave)}
.seg{display:inline-flex;border:1px solid var(--linea);border-radius:999px;overflow:hidden;margin:2px 0 8px}
.seg button{border:0;background:var(--papel);color:var(--tinta);padding:4px 11px;font:inherit;font-size:.82rem;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--banda);font-weight:600}
.tabla{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.9rem;font-variant-numeric:tabular-nums}
td,th{padding:6px 4px;border-top:1px solid var(--linea);text-align:left;vertical-align:top}
th{color:var(--suave);font-weight:600}td.n,th.n{text-align:right;white-space:nowrap}
.pronos{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px}
.pronos div{border:1px solid var(--linea);border-radius:10px;padding:8px}
.pronos b{display:block;font-family:var(--f-titulo);font-size:1.15rem;font-variant-numeric:tabular-nums}
.alerta{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;padding:10px 0;border-top:1px solid var(--linea)}
.alerta:first-child{border-top:0}
footer{margin-top:28px;color:var(--suave);font-size:.86rem}footer p{margin:.5rem 0;max-width:70ch}
code{font-size:.78rem;word-break:break-all}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style>
<main>
<header>
  <p class="lugar" id="lugar"></p>
  <h1>NowMarket</h1>
  <p class="sub" id="sub"></p>
</header>
<nav aria-label="Vistas">
  <a href="#este-mes" data-v="este-mes">Este mes</a>
  <a href="#producto" data-v="producto">Producto</a>
  <a href="#canasta" data-v="canasta">Canasta</a>
  <a href="#tenderos" data-v="tenderos">Tenderos</a>
</nav>

<section id="v-este-mes">
  <div class="bloque"><h2 id="resumen"></h2>
    <p class="nota">Cada producto comparado con la mediana de sus 12 meses anteriores; ±10 % o más cuenta como barato o caro. Toque un producto para ver su historia y su pronóstico.</p>
    <div class="chips" id="grupos"></div></div>
  <div class="bloque"><h3>Más baratos que de costumbre</h3><ul class="pizarra" id="l-barato"></ul></div>
  <div class="bloque"><h3>Más caros que de costumbre</h3><ul class="pizarra" id="l-caro"></ul></div>
</section>

<section id="v-producto">
  <div class="bloque"><label for="buscar">Producto</label>
    <input id="buscar" list="opciones" placeholder="Escriba, p. ej. papa, tomate, mora" autocomplete="off">
    <datalist id="opciones"></datalist></div>
  <div class="bloque" id="p-resumen"></div>
  <div class="bloque"><h3>Precio mes a mes y próximos 3 meses</h3>
    <div class="seg" id="rango"><button data-a="3" aria-pressed="true">3 años</button><button data-a="99" aria-pressed="false">Desde 2013</button></div>
    <div id="g-serie"></div><div class="leyenda" id="ley-serie"></div></div>
  <div class="bloque"><h3>¿En qué meses suele estar caro?</h3><div id="g-perfil"></div><p class="nota" id="n-perfil"></p></div>
  <div class="bloque" id="p-relacion"></div>
</section>

<section id="v-canasta">
  <div class="bloque" id="c-resumen"></div>
  <div class="bloque"><h3>Costo mayorista de la canasta</h3><div id="g-canasta"></div><div class="leyenda" id="ley-canasta"></div></div>
  <div class="bloque"><h3>Ajustar a un presupuesto</h3>
    <label for="presupuesto">Presupuesto mensual a precio mayorista</label>
    <input id="presupuesto" type="number" inputmode="numeric" min="0" step="5000">
    <div id="c-ajuste"></div></div>
  <div class="bloque"><h3>Qué lleva</h3><div class="tabla" id="c-tabla"></div></div>
</section>

<section id="v-tenderos">
  <div class="bloque"><h2 id="t-titulo"></h2><p class="nota" id="t-nota"></p><div id="t-alertas"></div></div>
  <div class="bloque"><h3>¿Qué tan bien acierta?</h3><div class="tabla" id="t-modelos"></div><p class="nota" id="t-modelos-nota"></p></div>
</section>

<footer id="pie"></footer>
</main>
<script>
const D = /*DATOS*/null;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pesos = v => v == null ? '—' : '$' + Math.round(v).toLocaleString('es-CO');
const pct = (v, signo = true) => v == null ? '—' : (signo && v > 0 ? '+' : '') + (v * 100).toFixed(0).replace('-', '−') + ' %';
const pct1 = v => v == null ? '—' : (v * 100).toFixed(1).replace('.', ',') + ' %';
const UNI = {kg:'kg', unidad:'unidad', litro:'litro'}, UNIS = {kg:'kg', unidad:'unidades', litro:'litros'};
const MES_L = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const mesTxt = ym => { const [y, m] = ym.split('-').map(Number); return MES_L[m - 1] + ' de ' + y; };
const mesCorto = ym => { const [y, m] = ym.split('-').map(Number); return D.meses[m - 1] + ' ' + String(y).slice(2); };
const idx = ym => { const [y, m] = ym.split('-').map(Number); return y * 12 + m - 1; };
const mesNum = +D.mes.split('-')[1] - 1, sigMes = (mesNum + 1) % 12;
const porId = Object.fromEntries(D.productos.map(p => [p.id, p]));
$('lugar').textContent = D.rotulo;
$('sub').textContent = 'Precios mayoristas de ' + mesTxt(D.mes) + ' · SIPSA, DANE';

// ---------- vistas con enlace propio (#este-mes, #producto, #canasta, #tenderos)
const VISTAS = ['este-mes', 'producto', 'canasta', 'tenderos'];
function ver(v, subir = true){
  if (!VISTAS.includes(v)) v = 'este-mes';
  document.querySelectorAll('nav a').forEach(a => { if (a.dataset.v === v) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  document.querySelectorAll('section').forEach(s => s.classList.toggle('activa', s.id === 'v-' + v));
  if (subir) window.scrollTo(0, 0);
}
window.addEventListener('hashchange', () => ver(location.hash.slice(1)));

function consejoTxt(p){
  if (!D.validacion.mostrar || !p.consejo) return '';
  return (p.consejo > 0 ? 'Suele subir' : 'Suele bajar') + ' en ' + MES_L[sigMes] + ' (' + pct(p.cambio) + ' típico)';
}

// ---------- vista: este mes
let grupo = 'Todos';
const grupos = ['Todos', ...[...new Set(D.productos.map(p => p.grupo))].sort((a, b) => a.localeCompare(b, 'es'))];
$('grupos').innerHTML = grupos.map(g => `<button type="button" aria-pressed="${g === grupo}">${esc(g)}</button>`).join('');
$('grupos').querySelectorAll('button').forEach(b => b.onclick = () => { grupo = b.textContent; pintarLista(); });
function fila(p){
  const c = consejoTxt(p);
  return `<li data-id="${esc(p.id)}" tabindex="0"><div><div class="nom">${esc(p.nombre)}</div><div class="sub">${pesos(p.precio)} por ${UNI[p.unidad]}${c ? ' · ' + esc(c) : ''}</div></div>
    <div class="num ${p.estado}">${pct(p.var12)}<div class="sub">vs. su año</div></div></li>`;
}
function pintarLista(){
  $('grupos').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.textContent === grupo));
  const ps = D.productos.filter(p => grupo === 'Todos' || p.grupo === grupo);
  const ba = ps.filter(p => p.estado === 'barato').sort((a, b) => a.var12 - b.var12);
  const ca = ps.filter(p => p.estado === 'caro').sort((a, b) => b.var12 - a.var12);
  $('resumen').textContent = `${ba.length} ${ba.length === 1 ? 'producto está' : 'productos están'} más baratos que de costumbre y ${ca.length} más caros`;
  $('l-barato').innerHTML = ba.slice(0, 10).map(fila).join('') || '<li class="nota">Ninguno en este grupo.</li>';
  $('l-caro').innerHTML = ca.slice(0, 10).map(fila).join('') || '<li class="nota">Ninguno en este grupo.</li>';
  document.querySelectorAll('ul.pizarra li[data-id]').forEach(li => {
    const ir = () => { elegir(li.dataset.id); location.hash = 'producto'; };
    li.onclick = ir; li.onkeydown = e => { if (e.key === 'Enter') ir(); };
  });
}
pintarLista();

// ---------- gráficas SVG (una sola escala por gráfica; texto con los colores del tema)
function grafica(series, {ancho = 360, alto = 220, desde = null, banda = null, mediana = null} = {}){
  const m = {l: 58, r: 16, t: 10, b: 22};
  const pts = series.map(s => { const o = []; if (!s.datos) return o;
    s.datos.v.forEach((v, k) => { const i = s.datos.ini + k; if (v != null && (desde == null || i >= desde)) o.push([i, v]); }); return o; });
  const extra = [...(banda || []).flatMap(b => [[b[0], b[1]], [b[0], b[2]]]), ...(mediana || [])];
  const todos = [...pts.flat(), ...extra]; if (!todos.length) return '<p class="nota">Sin datos.</p>';
  const x0 = Math.min(...todos.map(p => p[0])), x1 = Math.max(...todos.map(p => p[0]));
  let y0 = Math.min(...todos.map(p => p[1])), y1 = Math.max(...todos.map(p => p[1]));
  const pad = (y1 - y0) * .08 || y1 * .1; y0 = Math.max(0, y0 - pad); y1 += pad;
  const X = i => m.l + (i - x0) / Math.max(1, x1 - x0) * (ancho - m.l - m.r), Y = v => m.t + (1 - (v - y0) / (y1 - y0)) * (alto - m.t - m.b);
  let g = '';
  for (let k = 0; k <= 4; k++){ const v = y0 + (y1 - y0) * k / 4, y = Y(v);
    g += `<line x1="${m.l}" x2="${ancho - m.r}" y1="${y}" y2="${y}" stroke="var(--linea)"/><text x="${m.l - 6}" y="${y + 4}" text-anchor="end">${pesos(v)}</text>`; }
  const anios = (x1 - x0 + 1) / 12, paso = Math.max(1, Math.ceil(anios / 4)) * 12;
  for (let i = x0 - (x0 % 12) + 12 * (x0 % 12 ? 1 : 0); i <= x1; i += paso) g += `<line x1="${X(i)}" x2="${X(i)}" y1="${alto - m.b}" y2="${alto - m.b + 4}" stroke="var(--suave)"/><text x="${X(i)}" y="${alto - 6}" text-anchor="${X(i) > ancho - m.r - 14 ? 'end' : 'middle'}">${Math.floor(i / 12)}</text>`;
  if (banda && banda.length){
    const arriba = banda.map(b => `${X(b[0]).toFixed(1)},${Y(b[2]).toFixed(1)}`), abajo = banda.slice().reverse().map(b => `${X(b[0]).toFixed(1)},${Y(b[1]).toFixed(1)}`);
    g += `<polygon points="${arriba.concat(abajo).join(' ')}" fill="var(--acento-suave)" stroke="none"/>`;
  }
  series.forEach((s, k) => { const p = pts[k]; if (!p.length) return; let d = '';
    p.forEach(([i, v], j) => { const salto = j && i - p[j - 1][0] > 1; d += (j === 0 || salto ? 'M' : 'L') + X(i).toFixed(1) + ',' + Y(v).toFixed(1); });
    g += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.grosor || 2}" ${s.punteada ? 'stroke-dasharray="4 3"' : ''}/>`;
    if (s.ultimo){ const [i, v] = p[p.length - 1]; g += `<circle cx="${X(i)}" cy="${Y(v)}" r="3.5" fill="${s.color}"/>`; } });
  if (mediana && mediana.length){
    g += `<path d="${mediana.map(([i, v], j) => (j ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(v).toFixed(1)).join('')}" fill="none" stroke="var(--acento)" stroke-width="2" stroke-dasharray="5 4"/>`;
    const [i, v] = mediana[mediana.length - 1]; g += `<circle cx="${X(i)}" cy="${Y(v)}" r="3" fill="var(--papel)" stroke="var(--acento)" stroke-width="2"/>`;
  }
  return `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Precio mes a mes">${g}</svg>`;
}
function barrasPerfil(perfil, {ancho = 360, alto = 200} = {}){
  const m = {l: 44, r: 4, t: 10, b: 22}, ef = perfil.efecto.map(x => Math.expm1(x)), er = perfil.error;
  const lim = Math.max(.05, ...ef.map((v, i) => Math.abs(v) + 2 * er[i])) * 1.05;
  const w = (ancho - m.l - m.r) / 12, Y = v => m.t + (1 - (v + lim) / (2 * lim)) * (alto - m.t - m.b);
  let g = '';
  [-lim, -lim / 2, 0, lim / 2, lim].forEach(v => g += `<line x1="${m.l}" x2="${ancho - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--linea)" ${v === 0 ? '' : 'stroke-dasharray="2 3"'}/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${pct(v)}</text>`);
  ef.forEach((v, i) => { const x = m.l + i * w + w * .18, bw = w * .64, y = Y(Math.max(v, 0)), h = Math.abs(Y(v) - Y(0));
    const color = v >= 0 ? 'var(--caro)' : 'var(--barato)', op = (i === mesNum || i === sigMes) ? 1 : .45;
    g += `<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(h, 1)}" fill="${color}" opacity="${op}" rx="2"/>`;
    const lo = Math.expm1(perfil.efecto[i] - 2 * er[i]), hi = Math.expm1(perfil.efecto[i] + 2 * er[i]), cx = x + bw / 2;
    g += `<line x1="${cx}" x2="${cx}" y1="${Y(hi)}" y2="${Y(lo)}" stroke="var(--suave)" stroke-width="1"/>`;
    g += `<text x="${cx}" y="${alto - 6}" text-anchor="middle" style="${i === mesNum || i === sigMes ? 'font-weight:700;fill:var(--tinta)' : ''}">${D.meses[i]}</text>`; });
  return `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Meses en que suele estar caro o barato">${g}</svg>`;
}

// ---------- vista: un producto
const opciones = [...D.productos].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
$('opciones').innerHTML = opciones.map(p => `<option value="${esc(p.nombre)}">`).join('');
let actual = null, anios = 3;
function elegir(id){ actual = porId[id]; if (!actual) return; $('buscar').value = actual.nombre; pintarProducto(); }
$('buscar').addEventListener('change', e => { const p = D.productos.find(x => x.nombre.toLowerCase() === e.target.value.trim().toLowerCase()); if (p) elegir(p.id); });
$('rango').querySelectorAll('button').forEach(b => b.onclick = () => { anios = +b.dataset.a;
  $('rango').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); pintarProducto(); });
function estadoTxt(p){ return {barato: 'Más barato que de costumbre', caro: 'Más caro que de costumbre', normal: 'En su precio de costumbre', sin_referencia: 'Sin historia suficiente para comparar'}[p.estado]; }
function pintarProducto(){
  const p = actual; if (!p) return;
  const c = consejoTxt(p), pr = p.pron;
  let pronHtml = '<p class="nota">Pronóstico validado solo para los 18 productos de la canasta de referencia.</p>';
  if (pr && pr.length){
    pronHtml = '<div class="pronos">' + pr.map(f => `<div><span class="sub">${mesCorto(f.mes)}</span><b>${pesos(f.q50)}</b><span class="sub">${pesos(f.q10)} a ${pesos(f.q90)}</span></div>`).join('') + '</div>'
      + (pr.every(f => f.modelo === 'ingenuo')
        ? '<p class="nota">Lo más probable y el rango donde cae 8 de cada 10 veces. Se muestra el precio actual con su rango calibrado, porque en la validación ningún modelo le ganó de forma comprobada en 1, 2 ni 3 meses.</p>'
        : '<p class="nota">Lo más probable y el rango donde cae 8 de cada 10 veces. Donde un modelo le ganó de forma comprobada al precio actual se usa ese modelo; en los demás meses se muestra el precio actual con su rango.</p>');
  }
  $('p-resumen').innerHTML = `<h2>${esc(p.nombre)}</h2><div class="cifra-grande">${pesos(p.precio)} <span class="sub">por ${UNI[p.unidad]}</span></div>
    <p><b class="${p.estado}">${estadoTxt(p)}</b>: ${pct(p.var12)} frente a la mediana de su último año (${pesos(p.mediana)}). Frente a ${MES_L[mesNum]} del año pasado: ${pct(p.anual)}.</p>
    ${c ? `<p><b>${esc(c)}.</b> <span class="nota">Patrón de años anteriores.</span></p>` : ''}
    ${pronHtml}
    <p class="nota">Origen del precio: <code>${esc(p.origen)}</code></p>`;
  const ultimo = p.serie.ini + p.serie.v.length - 1, desde = anios >= 99 ? null : ultimo - anios * 12 + 1;
  const series = [{datos: p.serie, color: 'var(--acento)', grosor: 2.2, ultimo: true}];
  const comps = Object.keys(p.comp || {});
  comps.forEach(n => series.push({datos: p.comp[n], color: 'var(--comp)', grosor: 1.5, punteada: true}));
  let banda = null, mediana = null;
  if (pr && pr.length){
    banda = [[ultimo, p.precio, p.precio], ...pr.map(f => [idx(f.mes), f.q10, f.q90])];
    mediana = [[ultimo, p.precio], ...pr.map(f => [idx(f.mes), f.q50])];
  }
  $('g-serie').innerHTML = grafica(series, {desde, banda, mediana});
  $('ley-serie').innerHTML = '<span><i></i>Corabastos</span>' + comps.map(n => `<span><i class="comp"></i>${esc(n.replace('Bogotá, D.C., ', ''))}</span>`).join('')
    + (pr && pr.length ? '<span><i class="banda"></i>Pronóstico (80 %)</span>' : '');
  if (p.perfil){
    $('g-perfil').innerHTML = barrasPerfil(p.perfil);
    $('n-perfil').textContent = `Cuánto suele estar cada mes por encima (rojo) o por debajo (verde) de su tendencia, con ${Math.min(...p.perfil.anios)} a ${Math.max(...p.perfil.anios)} años de datos. La raya es ±2 errores estándar. Resaltados: ${MES_L[mesNum]} y ${MES_L[sigMes]}.`;
  } else { $('g-perfil').innerHTML = ''; $('n-perfil').textContent = 'No hay años suficientes para estimar su temporada.'; }
  const partes = [];
  if (p.nivel) partes.push(`<p><b>Cambio de nivel desde ${mesTxt(p.nivel.fecha)}:</b> el precio, sin contar la temporada, pasó a estar ${pct(p.nivel.cambio)} respecto al tramo anterior. Es más de lo que el detector encuentra por azar en 95 de cada 100 series sin cambio real (umbral ${pct(p.nivel.umbral, false)}).</p>`);
  const sus = (D.sustitutos.find(g => g.includes(p.id)) || []).filter(x => x !== p.id && porId[x] && porId[x].unidad === p.unidad);
  if (sus.length) partes.push('<p><b>Puede reemplazarlo con:</b></p><ul class="pizarra">' + sus.map(x => { const s = porId[x];
    return `<li data-id="${esc(x)}" tabindex="0"><div><div class="nom">${esc(s.nombre)}</div><div class="sub">${estadoTxt(s)}</div></div><div class="num">${pesos(s.precio)}<div class="sub">${s.precio < p.precio ? 'más barato' : 'más caro'}</div></div></li>`; }).join('') + '</ul>');
  if (p.vecinos.length) partes.push(`<p class="nota">Se mueve con: ${p.vecinos.map(v => `${esc(porId[v.id] ? porId[v.id].nombre : v.nombre)} (ρ = ${v.rho.toFixed(2).replace('.', ',')})`).join(' · ')}. Correlación de los cambios mensuales sin la temporada, 2013–2026.</p>`);
  $('p-relacion').innerHTML = partes.length ? '<h3>Relacionados</h3>' + partes.join('') : '<h3>Relacionados</h3><p class="nota">Sin sustitutos registrados ni productos que se muevan con este.</p>';
  $('p-relacion').querySelectorAll('li[data-id]').forEach(li => li.onclick = () => elegir(li.dataset.id));
}
elegir((D.productos.find(p => p.pron && p.estado === 'caro') || D.productos.find(p => p.pron) || D.productos[0]).id);

// ---------- vista: canasta
const C = D.canasta;
function pronCanasta(){
  let q10 = 0, q50 = 0, q90 = 0, mes = null;
  for (const c of C.componentes){ const f = (porId[c.producto_id]?.pron || []).find(x => x.h === 1); if (!f) return null;
    q10 += f.q10 * c.cantidad; q50 += f.q50 * c.cantidad; q90 += f.q90 * c.cantidad; mes = f.mes; }
  return {q10, q50, q90, mes};
}
(function(){
  const v = C.costo ? C.costo.v : [], ult = v.length - 1;
  if (ult < 0){ $('c-resumen').innerHTML = '<p>No hay meses con todos los productos.</p>'; return; }
  const iUlt = C.costo.ini + ult, hace = v[ult - 12], pc = pronCanasta();
  $('c-resumen').innerHTML = `<h2>${esc(C.nombre)}</h2><div class="cifra-grande">${pesos(v[ult])}</div>
    <p>Costo a precio mayorista de Corabastos en ${MES_L[iUlt % 12]} de ${Math.floor(iUlt / 12)}. ${hace ? `Hace un año: ${pesos(hace)} (${pct(v[ult] / hace - 1)}).` : ''}</p>
    ${pc ? `<p><b>${mesTxt(pc.mes)}:</b> lo más probable ${pesos(pc.q50)} (entre ${pesos(pc.q10)} y ${pesos(pc.q90)}).</p>` : ''}
    <p class="nota">En tienda costará más (transporte y margen). Sirve para ver si la canasta sube o baja, no para presupuestar al peso. El rango del próximo mes suma los rangos de cada producto, así que es amplio.</p>`;
  const banda = pc ? [[iUlt, v[ult], v[ult]], [idx(pc.mes), pc.q10, pc.q90]] : null, mediana = pc ? [[iUlt, v[ult]], [idx(pc.mes), pc.q50]] : null;
  $('g-canasta').innerHTML = grafica([{datos: C.costo, color: 'var(--acento)', grosor: 2.2, ultimo: true}], {banda, mediana});
  $('ley-canasta').innerHTML = '<span><i></i>Costo de cada mes, sin descontar inflación</span>' + (pc ? '<span><i class="banda"></i>Próximo mes</span>' : '');
  $('c-tabla').innerHTML = `<table><tr><th>Producto</th><th class="n">Cantidad</th><th class="n">Precio</th><th class="n">Subtotal</th></tr>` +
    C.componentes.map(c => `<tr title="Origen: ${esc(c.origen)}"><td>${esc(c.producto)}</td><td class="n">${c.cantidad.toLocaleString('es-CO')} ${c.cantidad === 1 ? UNI[c.unidad] : UNIS[c.unidad]}</td><td class="n">${pesos(c.precio)}</td><td class="n">${pesos(c.precio * c.cantidad)}</td></tr>`).join('') +
    `</table><p class="nota">Cantidades supuestas para un hogar de 4 personas (config/canasta.yaml). Sin carnes: Corabastos dejó de reportarlas en 2024.</p>`;
  const entrada = $('presupuesto');
  entrada.value = Math.floor(v[ult] * 0.92 / 5000) * 5000;
  const ajustar = () => {
    const meta = +entrada.value || 0;
    const precioHoy = c => (porId[c.producto_id] ? porId[c.producto_id].precio : c.precio);   // mismo mes que los sustitutos
    let total = C.componentes.reduce((s, c) => s + precioHoy(c) * c.cantidad, 0);
    const cambios = [];
    const opciones = C.componentes.map(c => {
      const sus = (D.sustitutos.find(g => g.includes(c.producto_id)) || []).filter(x => x !== c.producto_id && porId[x] && porId[x].unidad === c.unidad && porId[x].precio < precioHoy(c));
      if (!sus.length) return null;
      const mejor = sus.map(x => porId[x]).sort((a, b) => a.precio - b.precio)[0];
      return {c, s: mejor, ahorro: (precioHoy(c) - mejor.precio) * c.cantidad};
    }).filter(Boolean).sort((a, b) => b.ahorro - a.ahorro);
    for (const o of opciones){ if (total <= meta) break; total -= o.ahorro; cambios.push(o); }
    let html = '';
    if (!cambios.length && total <= meta) html = `<p>La canasta cabe en ${pesos(meta)} sin cambios. Sobran ${pesos(meta - total)}.</p>`;
    else {
      html = cambios.length ? '<ul class="pizarra">' + cambios.map(o => `<li><div><div class="nom">${esc(o.c.producto)} → ${esc(o.s.nombre)}</div><div class="sub">${pesos(precioHoy(o.c))} → ${pesos(o.s.precio)} por ${UNI[o.c.unidad]}</div></div><div class="num barato">−${pesos(o.ahorro)}</div></li>`).join('') + '</ul>' : '';
      html += total <= meta ? `<p>Con estos cambios la canasta cuesta ${pesos(total)} y cabe en el presupuesto.</p>`
        : cambios.length ? `<p>Aun con todos los reemplazos cuesta ${pesos(total)}: faltan ${pesos(total - meta)}. Habría que reducir cantidades.</p>`
        : `<p>No hay sustitutos más baratos este mes. La canasta cuesta ${pesos(total)}: faltan ${pesos(total - meta)}. Habría que reducir cantidades.</p>`;
    }
    $('c-ajuste').innerHTML = html + '<p class="nota">Reemplaza primero lo que más ahorra, solo con sustitutos de la misma unidad (config/sustitutos.yaml) y al precio de este mes.</p>';
  };
  entrada.addEventListener('input', ajustar); ajustar();
})();

// ---------- vista: tenderos
(function(){
  const A = D.alertas, M = D.modelos;
  const pr1 = D.productos.map(p => (p.pron || []).find(f => f.h === 1)).find(Boolean);
  const mes = A.length ? A[0].mes : (pr1 ? pr1.mes : '');
  $('t-titulo').textContent = mes ? `Qué esperar en ${mesTxt(mes)}` : 'Qué esperar el próximo mes';
  $('t-nota').textContent = 'Pronóstico a un mes para los 18 productos de la canasta. Sube o baja "lo más probable" si la mitad del rango se mueve 5 % o más; "con al menos 90 %" si todo el rango queda de un solo lado del precio actual.';
  const NIV = {alza_segura: ['caro', 'Sube'], alza_probable: ['caro', 'Sube'], baja_segura: ['barato', 'Baja'], baja_probable: ['barato', 'Baja']};
  $('t-alertas').innerHTML = A.length ? A.map(a => `<div class="alerta"><span class="pill ${NIV[a.nivel][0]}">${NIV[a.nivel][1]}</span><div><b>${esc(a.producto)}</b><div class="sub">${esc(a.texto)}</div></div></div>`).join('')
    : (pr1 && pr1.modelo === 'ingenuo'
      ? '<p>Sin alertas. A 1 mes se usa el precio actual con su rango (ningún modelo le ganó de forma comprobada), así que solo habría alerta si todo el rango quedara de un lado del precio actual, y hoy no pasa en ningún producto.</p>'
      : '<p>Ningún producto de la canasta tiene un cambio esperado de 5 % o más.</p>');
  if (M.prueba){
    $('t-modelos').innerHTML = '<table><tr><th>A</th><th>Método</th><th class="n">Error típico</th><th class="n">Cubrió</th></tr>' +
      M.prueba.map(r => `<tr><td>${r.h} ${r.h === 1 ? 'mes' : 'meses'}</td><td>${esc(r.corto || r.nombre)}</td><td class="n">${pct1(r.mae_pct)}</td><td class="n">${pct1(r.cobertura)}</td></tr>`).join('') + '</table>';
    $('t-modelos-nota').textContent = M.nota || '';
  } else $('t-modelos').innerHTML = '<p class="nota">Aún no se han validado modelos.</p>';
})();

// ---------- pie
const V = D.validacion;
$('pie').innerHTML = `
  <p><b>Precio mayorista no es precio de tienda.</b> SIPSA mide lo que se paga en la central de abastos, en pesos de cada mes (sin descontar inflación). Úselo para ver si algo sube o baja, no como precio final.</p>
  <p><b>Pronósticos:</b> ${esc(D.modelos.resumen || 'sin pronóstico validado.')}</p>
  <p><b>Consejo de temporada:</b> ${V.mostrar ? `se muestra porque, probado mes a mes de ${V.desde} a ${V.hasta} sin mirar el futuro, acertó si el precio subía o bajaba el ${pct1(V.tasa)} de ${V.n.toLocaleString('es-CO')} veces (IC 95 %: ${pct1(V.lo)} a ${pct1(V.hi)}), frente a ${pct1(V.base)} de repetir lo del año anterior.`
    : `no se muestra: en la prueba sin mirar el futuro acertó ${pct1(V.tasa)}, sin superar la línea base (${pct1(V.base)}) o el mínimo de ${pct1(V.minimo)}.`}</p>
  <p>Fuente: Departamento Administrativo Nacional de Estadística (DANE), SIPSA, series históricas mensuales de precios mayoristas y de abastecimiento; índice ONI de la NOAA. Cada precio indica el archivo, la hoja y la fila de donde salió. No es asesoría financiera.</p>
  <p>NowMarket v${esc(D.version)} · generado ${esc(D.generado.replace('T', ' '))}</p>`;
ver(location.hash.slice(1), false);
</script>"""
