"""Utilidades compartidas por el motor."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Huella SHA-256 de un archivo, leída por bloques."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def renombrar_con_reintentos(origen: Path, destino: Path, intentos: int = 6) -> None:
    """Publica un archivo o una carpeta ya preparados, con reintentos.

    En Windows el antivirus o el indexador pueden bloquear un instante lo
    recién escrito y el renombrado falla con «Acceso denegado». Se reintenta
    unos segundos antes de rendirse. La publicación sigue siendo un único
    paso: o se renombra entero o no se publica nada.
    """
    for intento in range(intentos):
        try:
            origen.rename(destino)
            return
        except PermissionError:
            if intento == intentos - 1:
                raise
            time.sleep(0.2 * (intento + 1))
