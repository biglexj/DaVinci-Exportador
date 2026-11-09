"""Ejecuta la línea de comandos del exportador.

    python -m davinci_exportador --help
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
