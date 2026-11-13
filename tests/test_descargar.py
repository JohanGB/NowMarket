"""Pruebas del script de descarga. No usan internet: levantan un servidor HTTP local."""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from mercado_al_dia.ingesta import descargar as d

XLSX_FALSO = b"PK\x03\x04" + b"contenido-de-prueba" * 50
ONI_FALSO = b"SEAS  YR   TOTAL   ANOM\n DJF 1950   24.72  -1.53\n"


class _Servidor:
    """Servidor HTTP local. rutas: {"/ruta": [(estado, cuerpo), ...]} (el último se repite)."""

    def __init__(self) -> None:
        self.rutas: dict[str, list[tuple[int, bytes]]] = {}
        self.conteo: dict[str, int] = {}
        servidor = self

        class Manejador(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                n = servidor.conteo.get(self.path, 0)
                servidor.conteo[self.path] = n + 1
                respuestas = servidor.rutas.get(self.path, [(404, b"no existe")])
                estado, cuerpo = respuestas[min(n, len(respuestas) - 1)]
                self.send_response(estado)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *args):  # silencio
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()

    def cerrar(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def servidor(monkeypatch):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    s = _Servidor()
    yield s
    s.cerrar()


@pytest.fixture
def proyecto(tmp_path, servidor):
    """Crea un proyecto mínimo con dos fuentes que apuntan al servidor local."""
    servidor.rutas["/serie.xlsx"] = [(200, XLSX_FALSO)]
    servidor.rutas["/oni.txt"] = [(200, ONI_FALSO)]
    config = {
        "descarga": {"tiempo_espera_s": 5, "reintentos": 3, "espera_entre_reintentos_s": 0},
        "fuentes": [
            {
                "id": "serie",
                "url": f"{servidor.base}/serie.xlsx",
                "destino": "sipsa/precios_mensual/serie.xlsx",
                "tipo": "xlsx",
            },
            {
                "id": "oni",
                "url": f"{servidor.base}/oni.txt",
                "destino": "exogenas/oni.txt",
                "tipo": "txt",
            },
        ],
    }
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "fuentes.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True), encoding="utf-8"
    )
    return tmp_path


def correr(raiz: Path, *extra: str) -> int:
    return d.main(["--raiz", str(raiz), *extra], dormir=lambda s: None)


def leer_manifiesto(raiz: Path) -> dict:
    return json.loads((raiz / "data" / "manifest.json").read_text(encoding="utf-8"))


def test_descarga_guarda_archivo_y_registra_manifiesto(proyecto, servidor):
    assert correr(proyecto) == 0
    archivo = proyecto / "data" / "raw" / "sipsa" / "precios_mensual" / "serie.xlsx"
    assert archivo.read_bytes() == XLSX_FALSO  # guardado sin modificar

    entrada = leer_manifiesto(proyecto)["archivos"]["sipsa/precios_mensual/serie.xlsx"]
    assert entrada["sha256"] == hashlib.sha256(XLSX_FALSO).hexdigest()
    assert entrada["bytes"] == len(XLSX_FALSO)
    assert entrada["url"] == f"{servidor.base}/serie.xlsx"
    assert entrada["origen"] == "descarga"
    assert entrada["fecha_descarga_utc"].endswith("Z")
    assert "exogenas/oni.txt" in leer_manifiesto(proyecto)["archivos"]
    # No quedan temporales .part
    assert not list((proyecto / "data" / "raw").rglob("*.part"))


def test_idempotente_no_vuelve_a_descargar(proyecto, servidor):
    assert correr(proyecto) == 0
    archivos_antes = leer_manifiesto(proyecto)["archivos"]
    assert correr(proyecto) == 0
    assert servidor.conteo["/serie.xlsx"] == 1  # la segunda corrida no consultó el servidor
    assert servidor.conteo["/oni.txt"] == 1
    assert leer_manifiesto(proyecto)["archivos"] == archivos_antes


def test_registra_archivo_descargado_a_mano(proyecto, servidor):
    manual = proyecto / "data" / "raw" / "sipsa" / "precios_mensual" / "serie.xlsx"
    manual.parent.mkdir(parents=True)
    manual.write_bytes(b"PK\x03\x04archivo-bajado-con-el-navegador")
    assert correr(proyecto, "--solo", "serie") == 0
    assert servidor.conteo.get("/serie.xlsx", 0) == 0
    entrada = leer_manifiesto(proyecto)["archivos"]["sipsa/precios_mensual/serie.xlsx"]
    assert entrada["origen"] == "manual"
    assert entrada["sha256"] == hashlib.sha256(manual.read_bytes()).hexdigest()


def test_alerta_si_el_crudo_fue_modificado_y_no_lo_toca(proyecto, servidor):
    assert correr(proyecto) == 0
    archivo = proyecto / "data" / "raw" / "sipsa" / "precios_mensual" / "serie.xlsx"
    sha_original = leer_manifiesto(proyecto)["archivos"]["sipsa/precios_mensual/serie.xlsx"]["sha256"]
    archivo.write_bytes(b"PK\x03\x04editado-a-mano")
    assert correr(proyecto) == 1
    assert archivo.read_bytes() == b"PK\x03\x04editado-a-mano"  # no se sobrescribe
    assert servidor.conteo["/serie.xlsx"] == 1
    assert (
        leer_manifiesto(proyecto)["archivos"]["sipsa/precios_mensual/serie.xlsx"]["sha256"]
        == sha_original
    )


def test_rechaza_pagina_html_en_lugar_de_xlsx(proyecto, servidor):
    servidor.rutas["/serie.xlsx"] = [(200, b"<!DOCTYPE html><html>Error</html>")]
    assert correr(proyecto, "--solo", "serie") == 1
    assert not (proyecto / "data" / "raw" / "sipsa" / "precios_mensual" / "serie.xlsx").exists()
    assert "sipsa/precios_mensual/serie.xlsx" not in leer_manifiesto(proyecto)["archivos"]
    assert not list((proyecto / "data" / "raw").rglob("*.part"))


def test_reintenta_ante_error_de_servidor(proyecto, servidor):
    servidor.rutas["/serie.xlsx"] = [(503, b"ocupado"), (500, b"error"), (200, XLSX_FALSO)]
    assert correr(proyecto, "--solo", "serie") == 0
    assert servidor.conteo["/serie.xlsx"] == 3


def test_no_reintenta_404_y_reporta_error(proyecto, servidor):
    servidor.rutas["/serie.xlsx"] = [(404, b"no existe")]
    assert correr(proyecto, "--solo", "serie") == 1
    assert servidor.conteo["/serie.xlsx"] == 1


def test_actualizar_guarda_nueva_version_sin_pisar_la_anterior(proyecto, servidor):
    assert correr(proyecto, "--solo", "serie") == 0
    nuevo = b"PK\x03\x04version-de-diciembre"
    servidor.rutas["/serie.xlsx"] = [(200, nuevo)]
    assert correr(proyecto, "--solo", "serie", "--actualizar") == 0
    carpeta = proyecto / "data" / "raw" / "sipsa" / "precios_mensual"
    assert (carpeta / "serie.xlsx").read_bytes() == XLSX_FALSO
    versiones = sorted(carpeta.glob("serie__*.xlsx"))
    assert len(versiones) == 1 and versiones[0].read_bytes() == nuevo
    archivos = leer_manifiesto(proyecto)["archivos"]
    clave_nueva = f"sipsa/precios_mensual/{versiones[0].name}"
    assert archivos[clave_nueva]["version_de"] == "sipsa/precios_mensual/serie.xlsx"
    assert archivos[clave_nueva]["sha256"] == hashlib.sha256(nuevo).hexdigest()

    # Sin cambios en el servidor: no se crea otra versión.
    assert correr(proyecto, "--solo", "serie", "--actualizar") == 0
    assert len(sorted(carpeta.glob("serie__*.xlsx"))) == 1


def test_config_rechaza_destino_fuera_de_data_raw(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "fuentes.yaml").write_text(
        yaml.safe_dump({"fuentes": [{"id": "x", "url": "http://x", "destino": "../fuera.txt"}]}),
        encoding="utf-8",
    )
    assert correr(tmp_path) == 2


def test_config_del_proyecto_es_valida():
    raiz = Path(__file__).resolve().parents[1]
    config = d.cargar_config(raiz / "config" / "fuentes.yaml")
    activas = [f for f in config["fuentes"] if f["activo"]]
    assert len(activas) == 13
    assert all(f["url"].startswith("https://") for f in activas)
