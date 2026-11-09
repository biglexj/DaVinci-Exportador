"""Punto de entrada único de DaVinci Exportador.

Este archivo solo orquesta: prepara las rutas de los dos paquetes del proyecto
y decide qué se ejecuta.

- Sin argumentos, abre la app de escritorio (Flet).
- Con ``build``, compila el ejecutable de escritorio y el instalador.
- Con otros argumentos, delega en la línea de comandos del motor.

El motor vive en ``src/davinci_exportador`` y la interfaz en ``src-flet``.
Ninguno de los dos se importa al cargar este archivo: solo cuando hace falta.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SRC = RAIZ / "src"
SRC_FLET = RAIZ / "src-flet"
SCRIPT_COMPILACION = RAIZ / "scripts" / "packaging" / "Build-Installer.ps1"


def _preparar_rutas() -> None:
    """Añade ``src`` y ``src-flet`` al ``sys.path`` de la sesion actual."""
    for ruta in (SRC, SRC_FLET):
        if ruta.is_dir() and str(ruta) not in sys.path:
            sys.path.insert(0, str(ruta))


def _compilar(argumentos: list[str]) -> int:
    """Compila el ejecutable de escritorio y el instalador de Windows."""
    if not SCRIPT_COMPILACION.is_file():
        print(f"No se encontró el script de compilación: {SCRIPT_COMPILACION}", file=sys.stderr)
        return 1
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        print("Se necesita PowerShell (pwsh) para compilar.", file=sys.stderr)
        return 1
    # -LocalOnly deja constancia de que la compilación no publica nada: la
    # publicación remota es una tarea explícita de Mise (`mise publish`).
    comando = [powershell, "-NoProfile", "-File", str(SCRIPT_COMPILACION), "-LocalOnly", *argumentos]
    return subprocess.call(comando, cwd=str(RAIZ))


def main(argv: list[str] | None = None) -> int:
    """Orquesta la app de escritorio, la compilacion o la linea de comandos."""
    argumentos = list(sys.argv[1:] if argv is None else argv)

    if argumentos and argumentos[0] == "build":
        return _compilar(argumentos[1:])

    _preparar_rutas()
    if argumentos:
        from davinci_exportador.cli import main as ejecutar_cli

        return ejecutar_cli(argumentos)

    from app.app import open_desktop

    open_desktop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
