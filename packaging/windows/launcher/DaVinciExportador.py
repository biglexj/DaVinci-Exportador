"""Punto de entrada del ejecutable de escritorio de DaVinci Exportador.

Este archivo es el script de entrada que PyInstaller convierte en
`DaVinciExportador.exe`. No contiene logica de la aplicacion: solo prepara las
rutas de los paquetes del proyecto y deja rastro si el arranque falla.

Reglas:
- No se modifica codigo de produccion (`src/` ni `src-flet/`).
- Los datos del usuario nunca se escriben junto al ejecutable: el registro
  de fallos va a `%USERPROFILE%\\.davinci_exportador\\logs`.
"""

import sys
import traceback
from pathlib import Path


def _base_dir() -> Path:
    """Directorio base de los recursos empaquetados."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _prepare_import_paths(base: Path) -> None:
    """En modo congelado los modulos ya vienen empaquetados; en modo fuente
    se anaden `src` y `src-flet` al `sys.path`."""
    for relative in ("src", "src-flet"):
        candidate = base / relative
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def _log_dir() -> Path:
    return Path.home() / ".davinci_exportador" / "logs"


def _log_failure(exc: BaseException) -> None:
    """Deja rastro del fallo sin depender de una consola visible."""
    try:
        log_dir = _log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "desktop-bundled.log").open("a", encoding="utf-8") as handle:
            handle.write("---- DaVinci Exportador (empaquetado) ----\n")
            handle.write(traceback.format_exc())
            handle.write("\n")
    except Exception:
        pass


def _prepare_streams() -> None:
    """En un ejecutable sin consola (PyInstaller en modo `windowed`) las
    salidas estandar valen None. Flet las usa para escribir mensajes y el
    cliente de escritorio se queda oculto sin ventana. Se redirigen al log."""
    if not getattr(sys, "frozen", False):
        return
    try:
        log_dir = _log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        stream = (log_dir / "desktop-bundled.log").open("a", encoding="utf-8")
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    except Exception:
        pass


def main() -> None:
    _prepare_streams()
    base = _base_dir()
    _prepare_import_paths(base)

    import app.app as desktop_app

    desktop_app.open_desktop()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        _log_failure(sys.exc_info()[1])
        raise
