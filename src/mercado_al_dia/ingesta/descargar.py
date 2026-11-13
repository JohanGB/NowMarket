"""Descarga las fuentes públicas listadas en config/fuentes.yaml.

Uso (desde la raíz del proyecto):

    python -m mercado_al_dia.ingesta.descargar
    python -m mercado_al_dia.ingesta.descargar --solo noaa_oni
    python -m mercado_al_dia.ingesta.descargar --actualizar   # vuelve a consultar el servidor
    python -m mercado_al_dia.ingesta.descargar --listar

Reglas:
- Los archivos se guardan sin modificar en data/raw/<destino>.
- Cada archivo queda registrado en data/manifest.json con URL, fecha y hora (UTC),
  tamaño en bytes y SHA-256.
- Es idempotente: si el archivo ya existe y su SHA-256 coincide con el manifiesto,
  no se vuelve a descargar (ni siquiera se consulta el servidor).
- Si el archivo existe pero no está en el manifiesto (descarga manual), se registra
  con origen "manual".
- Si el archivo existe y su SHA-256 NO coincide con el manifiesto, se reporta una
  alerta y no se toca: data/raw es inmutable.
- Con --actualizar se vuelve a descargar; si el contenido cambió en el servidor, la
  nueva versión se guarda con otro nombre (sufijo __AAAAMMDD) y nunca se sobrescribe
  la anterior.

Solo usa la biblioteca estándar más PyYAML.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import yaml

TAMANO_BLOQUE = 1024 * 1024
CAMPOS_OBLIGATORIOS = ("id", "url", "destino")

# Firmas de inicio de archivo para detectar que no llegó una página HTML de error.
FIRMAS: dict[str, tuple[bytes, ...]] = {
    "xlsx": (b"PK\x03\x04",),
    "zip": (b"PK\x03\x04",),
    "pdf": (b"%PDF",),
    "xls": (b"\xd0\xcf\x11\xe0",),
}

DESCARGA_POR_DEFECTO = {
    "tiempo_espera_s": 60,
    "reintentos": 3,
    "espera_entre_reintentos_s": 5,
    "user_agent": "mercado-al-dia/0.1 (descarga de datos publicos)",
}


class ErrorConfig(Exception):
    """Configuración inválida."""


class ErrorDescarga(Exception):
    """Falló la descarga de un archivo."""


class ErrorDefinitivo(ErrorDescarga):
    """Error que no vale la pena reintentar (p. ej. 404)."""


# --------------------------------------------------------------------------- utilidades


def ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(TAMANO_BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()


def imprimir(msg: str) -> None:
    print(msg, flush=True)


def ruta_segura(raiz_raw: Path, destino: str) -> Path:
    """Convierte un destino relativo (con '/') en ruta dentro de raiz_raw, sin escaparse."""
    p = PurePosixPath(destino.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ErrorConfig(f"Destino inválido (debe ser relativo y sin '..'): {destino!r}")
    return raiz_raw.joinpath(*p.parts)


# --------------------------------------------------------------------------- configuración


def cargar_config(ruta: Path) -> dict[str, Any]:
    if not ruta.is_file():
        raise ErrorConfig(f"No se encontró el archivo de configuración: {ruta}")
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    fuentes = datos.get("fuentes")
    if not isinstance(fuentes, list) or not fuentes:
        raise ErrorConfig("La configuración no tiene una lista 'fuentes'.")
    vistos_id: set[str] = set()
    vistos_destino: set[str] = set()
    for i, fuente in enumerate(fuentes, start=1):
        if not isinstance(fuente, dict):
            raise ErrorConfig(f"La fuente #{i} no es un diccionario.")
        faltan = [c for c in CAMPOS_OBLIGATORIOS if not fuente.get(c)]
        if faltan:
            raise ErrorConfig(f"A la fuente #{i} le faltan campos: {', '.join(faltan)}")
        if fuente["id"] in vistos_id:
            raise ErrorConfig(f"id repetido en la configuración: {fuente['id']}")
        destino = str(PurePosixPath(fuente["destino"].replace("\\", "/")))
        if destino in vistos_destino:
            raise ErrorConfig(f"destino repetido en la configuración: {destino}")
        ruta_segura(Path("."), destino)  # valida que no se escape de data/raw
        vistos_id.add(fuente["id"])
        vistos_destino.add(destino)
        fuente["destino"] = destino
        fuente.setdefault("activo", True)
        fuente.setdefault("tipo", PurePosixPath(destino).suffix.lstrip(".").lower())
    opciones = dict(DESCARGA_POR_DEFECTO)
    opciones.update(datos.get("descarga") or {})
    return {"descarga": opciones, "fuentes": fuentes}


# --------------------------------------------------------------------------- manifiesto


def cargar_manifiesto(ruta: Path) -> dict[str, Any]:
    if not ruta.is_file():
        return {"version": 1, "archivos": {}}
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    datos.setdefault("version", 1)
    datos.setdefault("archivos", {})
    return datos


def guardar_manifiesto(ruta: Path, manifiesto: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    manifiesto["actualizado_utc"] = ahora_utc()
    texto = json.dumps(manifiesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=".manifest.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        os.replace(tmp, ruta)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# --------------------------------------------------------------------------- descarga


def validar_contenido(ruta: Path, tipo: str) -> None:
    """Rechaza archivos vacíos o páginas HTML que llegan en lugar del archivo esperado."""
    with open(ruta, "rb") as f:
        inicio = f.read(512)
    if not inicio:
        raise ErrorDefinitivo("el servidor devolvió un archivo vacío")
    firmas = FIRMAS.get(tipo)
    if firmas and not inicio.startswith(firmas):
        raise ErrorDefinitivo(
            f"el contenido no parece un archivo .{tipo} (posible página HTML de error)"
        )
    if tipo not in ("html", "htm"):
        cabeza = inicio.lstrip().lower()
        if cabeza.startswith(b"<!doctype html") or cabeza.startswith(b"<html"):
            raise ErrorDefinitivo("el servidor devolvió una página HTML en lugar del archivo")


def descargar_a_temporal(
    url: str,
    carpeta: Path,
    opciones: dict[str, Any],
    dormir: Callable[[float], None] = time.sleep,
) -> Path:
    """Descarga `url` a un archivo temporal dentro de `carpeta` con reintentos moderados."""
    intentos = max(1, int(opciones["reintentos"]))
    espera = float(opciones["espera_entre_reintentos_s"])
    tiempo_espera = float(opciones["tiempo_espera_s"])
    carpeta.mkdir(parents=True, exist_ok=True)
    ultimo_error: Exception | None = None

    for intento in range(1, intentos + 1):
        fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=".descarga.", suffix=".part")
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": opciones["user_agent"]})
            with urllib.request.urlopen(req, timeout=tiempo_espera) as resp, open(
                tmp_path, "wb"
            ) as f:
                for bloque in iter(lambda: resp.read(TAMANO_BLOQUE), b""):
                    f.write(bloque)
            return tmp_path
        except urllib.error.HTTPError as e:
            tmp_path.unlink(missing_ok=True)
            if e.code in (408, 429) or e.code >= 500:
                ultimo_error = ErrorDescarga(f"HTTP {e.code} {e.reason}")
            else:
                raise ErrorDefinitivo(f"HTTP {e.code} {e.reason}") from e
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            tmp_path.unlink(missing_ok=True)
            motivo = getattr(e, "reason", e)
            ultimo_error = ErrorDescarga(f"error de conexión: {motivo}")
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        if intento < intentos:
            pausa = espera * (2 ** (intento - 1))
            imprimir(
                f"    intento {intento}/{intentos} falló ({ultimo_error}); "
                f"reintento en {pausa:.0f} s"
            )
            dormir(pausa)

    raise ErrorDescarga(f"falló tras {intentos} intentos: {ultimo_error}")


def _entrada(fuente: dict[str, Any], destino: str, ruta: Path, sha: str, origen: str) -> dict:
    return {
        "id": fuente["id"],
        "url": fuente["url"],
        "pagina_origen": fuente.get("pagina_origen"),
        "destino": destino,
        "tipo": fuente.get("tipo"),
        "origen": origen,
        "fecha_descarga_utc": ahora_utc(),
        "bytes": ruta.stat().st_size,
        "sha256": sha,
    }


def _ruta_version(ruta: Path) -> Path:
    marca = datetime.now(timezone.utc).strftime("%Y%m%d")
    candidata = ruta.with_name(f"{ruta.stem}__{marca}{ruta.suffix}")
    if candidata.exists():
        marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        candidata = ruta.with_name(f"{ruta.stem}__{marca}{ruta.suffix}")
    return candidata


def procesar_fuente(
    fuente: dict[str, Any],
    raiz_raw: Path,
    manifiesto: dict[str, Any],
    opciones: dict[str, Any],
    actualizar: bool = False,
    dormir: Callable[[float], None] = time.sleep,
) -> str:
    """Procesa una fuente y devuelve un estado corto. Lanza ErrorDescarga si falla."""
    destino = fuente["destino"]
    ruta = ruta_segura(raiz_raw, destino)
    archivos = manifiesto["archivos"]
    previa = archivos.get(destino)

    if ruta.exists():
        sha_local = sha256_de(ruta)
        if previa is None:
            archivos[destino] = _entrada(fuente, destino, ruta, sha_local, "manual")
            return "registrado_manual"
        if previa["sha256"] != sha_local:
            return "alerta_modificado"
        if not actualizar:
            return "sin_cambios"
        tmp = descargar_a_temporal(fuente["url"], ruta.parent, opciones, dormir)
        try:
            validar_contenido(tmp, fuente["tipo"])
            sha_nuevo = sha256_de(tmp)
            conocidos = {
                e["sha256"]
                for clave, e in archivos.items()
                if clave == destino or e.get("version_de") == destino
            }
            if sha_nuevo in conocidos:
                return "sin_cambios_en_servidor"
            nueva = _ruta_version(ruta)
            os.replace(tmp, nueva)
        finally:
            tmp.unlink(missing_ok=True)
        destino_nuevo = nueva.relative_to(raiz_raw).as_posix()
        entrada = _entrada(fuente, destino_nuevo, nueva, sha_nuevo, "descarga")
        entrada["version_de"] = destino
        archivos[destino_nuevo] = entrada
        return f"nueva_version -> {destino_nuevo}"

    tmp = descargar_a_temporal(fuente["url"], ruta.parent, opciones, dormir)
    try:
        validar_contenido(tmp, fuente["tipo"])
        sha_nuevo = sha256_de(tmp)
        os.replace(tmp, ruta)
    finally:
        tmp.unlink(missing_ok=True)
    entrada = _entrada(fuente, destino, ruta, sha_nuevo, "descarga")
    if previa is not None and previa["sha256"] != sha_nuevo:
        entrada["sha256_registrado_antes"] = previa["sha256"]
        archivos[destino] = entrada
        return "descargado_con_hash_distinto_al_registrado"
    archivos[destino] = entrada
    return "descargado"


# --------------------------------------------------------------------------- CLI


def _raiz_por_defecto() -> Path:
    cwd = Path.cwd()
    if (cwd / "config" / "fuentes.yaml").is_file():
        return cwd
    # src/mercado_al_dia/ingesta/descargar.py -> raíz del proyecto
    return Path(__file__).resolve().parents[3]


def _configurar_consola() -> None:
    # Evita errores de codificación en consolas cp1252 de Windows.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m mercado_al_dia.ingesta.descargar",
        description="Descarga las fuentes públicas a data/raw/ y las registra en data/manifest.json.",
    )
    p.add_argument("--raiz", type=Path, default=None, help="Raíz del proyecto (por defecto se detecta).")
    p.add_argument("--config", type=Path, default=None, help="Ruta del YAML de fuentes.")
    p.add_argument("--datos", type=Path, default=None, help="Carpeta de datos crudos (por defecto data/raw).")
    p.add_argument("--manifiesto", type=Path, default=None, help="Ruta del manifiesto (por defecto data/manifest.json).")
    p.add_argument("--solo", action="append", default=[], metavar="ID", help="Procesar solo esta fuente (repetible).")
    p.add_argument("--incluir-inactivas", action="store_true", help="Procesar también fuentes con activo: false.")
    p.add_argument("--actualizar", action="store_true", help="Volver a consultar el servidor aunque el archivo exista.")
    p.add_argument("--listar", action="store_true", help="Solo listar las fuentes configuradas.")
    return p


def main(argv: list[str] | None = None, dormir: Callable[[float], None] = time.sleep) -> int:
    _configurar_consola()
    args = construir_parser().parse_args(argv)
    raiz = (args.raiz or _raiz_por_defecto()).resolve()
    ruta_config = args.config or raiz / "config" / "fuentes.yaml"
    raiz_raw = args.datos or raiz / "data" / "raw"
    ruta_manifiesto = args.manifiesto or raiz / "data" / "manifest.json"

    try:
        config = cargar_config(ruta_config)
    except ErrorConfig as e:
        imprimir(f"ERROR de configuración: {e}")
        return 2

    fuentes = config["fuentes"]
    if args.solo:
        desconocidas = set(args.solo) - {f["id"] for f in fuentes}
        if desconocidas:
            imprimir(f"ERROR: ids desconocidos: {', '.join(sorted(desconocidas))}")
            return 2
        fuentes = [f for f in fuentes if f["id"] in args.solo]
    elif not args.incluir_inactivas:
        fuentes = [f for f in fuentes if f.get("activo", True)]

    if args.listar:
        for f in config["fuentes"]:
            marca = "activa  " if f.get("activo", True) else "inactiva"
            imprimir(f"[{marca}] {f['id']}: {f['url']} -> data/raw/{f['destino']}")
        return 0

    manifiesto = cargar_manifiesto(ruta_manifiesto)
    imprimir(f"Fuentes a procesar: {len(fuentes)}. Datos crudos en: {raiz_raw}")
    errores = 0
    alertas = 0
    for fuente in fuentes:
        imprimir(f"- {fuente['id']}")
        try:
            estado = procesar_fuente(
                fuente, raiz_raw, manifiesto, config["descarga"], args.actualizar, dormir
            )
        except ErrorDescarga as e:
            errores += 1
            imprimir(f"    ERROR: {e}")
            imprimir(f"    Descárguelo a mano desde: {fuente['url']}")
            imprimir(f"    y guárdelo como: {ruta_segura(raiz_raw, fuente['destino'])}")
            continue
        if estado == "alerta_modificado":
            alertas += 1
            imprimir(
                "    ALERTA: el archivo en disco no coincide con el SHA-256 del manifiesto. "
                "data/raw es inmutable: no se tocó. Revise si alguien lo editó."
            )
        else:
            entrada = manifiesto["archivos"].get(fuente["destino"], {})
            detalle = f" ({entrada.get('bytes', '?')} bytes)" if estado.startswith("descargado") else ""
            imprimir(f"    {estado}{detalle}")
        guardar_manifiesto(ruta_manifiesto, manifiesto)

    guardar_manifiesto(ruta_manifiesto, manifiesto)
    imprimir(
        f"Listo. Errores: {errores}. Alertas: {alertas}. Manifiesto: {ruta_manifiesto}"
    )
    return 1 if (errores or alertas) else 0


if __name__ == "__main__":
    sys.exit(main())
