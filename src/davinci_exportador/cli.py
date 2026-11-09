"""Línea de comandos del exportador.

Es el mismo motor que usa la app de escritorio, sin interfaz:

    python -m davinci_exportador listar 'D:\\Exportaciones\\Mis titulos.drb'
    python -m davinci_exportador exportar 'origen.drb' --salida 'destino'
    python -m davinci_exportador empaquetar 'Templates' --salida 'paquete.drfx'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .conversion import VERSION, export_titles, make_title
from .empaquetado import package_templates
from .errores import ExportError
from .lectura import read_compositions_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="davinci-exportador",
        description="Exportador de plantillas Fusion y empaquetador DRFX, sin dependencias externas.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("listar", help="Inventariar composiciones sin modificar archivos.")
    inspect.add_argument("origen", type=Path)
    export = commands.add_parser("exportar", help="Convertir títulos a .setting en una carpeta nueva.")
    export.add_argument("origen", type=Path)
    export.add_argument("--salida", type=Path, required=True)
    export.add_argument("--carpeta", action="append", dest="folders", help="Nombre exacto; repetir para varias carpetas.")
    export.add_argument("--config", type=Path, help="Reglas JSON de creador, colección y nombres.")
    export.add_argument("--permitir-medios-externos", action="store_true")
    pack = commands.add_parser("empaquetar", help="Crear un DRFX desde una carpeta que contiene Edit/.")
    pack.add_argument("carpeta", type=Path)
    pack.add_argument("--salida", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "listar":
            lectura = read_compositions_report(args.origen)
            result = []
            for comp in lectura.compositions:
                item = {"folder": comp.folder, "name": comp.name, "source": comp.source}
                try:
                    make_title(comp)
                    item["compatible"] = True
                    item["motivo"] = ""
                except ExportError as exc:
                    item["compatible"] = False
                    item["motivo"] = str(exc)
                result.append(item)
            for problema in lectura.problems:
                print(f"Aviso: {problema}", file=sys.stderr)
        elif args.command == "exportar":
            config = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config else {}
            result = export_titles(args.origen, args.salida, args.folders, config, args.permitir_medios_externos)
        else:
            result = package_templates(args.carpeta, args.salida)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ExportError, OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
