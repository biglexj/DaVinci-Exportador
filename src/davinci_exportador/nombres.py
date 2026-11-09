"""Reglas de nombres y carpetas de salida.

La atribución del creador se mantiene separada de la autoría de una
adaptación: las reglas se aplican por nombre exacto de carpeta y el motor no
adivina creadores.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errores import ExportError
from .modelo import Composition


def safe_component(value: str) -> str:
    """Convierte un nombre en un componente de ruta válido en Windows."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    if not value or value in {".", ".."}:
        raise ExportError("Nombre de archivo o carpeta vacío.")
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", value, re.I):
        value = "_" + value
    return value


def title_destination(comp: Composition, config: dict) -> tuple[Path, str]:
    """Calcula la ruta y el nombre final de un título según las reglas."""
    options = dict(config.get("defaults", {}))
    for rule in config.get("rules", []):
        if rule.get("folder") == comp.folder:
            options.update(rule)
    creator = options.get("creator", "Sin atribuir")
    collection = options.get("collection", "Títulos exportados")
    name = comp.name
    if options.get("strip_prefix") and name.startswith(options["strip_prefix"]):
        name = name[len(options["strip_prefix"]):]
    if options.get("replace_hyphens"):
        name = name.replace("-", " ")
    if options.get("title_case"):
        name = name.title()
    name = options.get("prefix", "") + name
    if options.get("credit"):
        name += " - " + options["credit"]
    parts = ["Edit", "Titles", safe_component(creator), safe_component(collection)]
    # null elimina el nivel; el valor por defecto conserva la carpeta de origen.
    subgroup = options.get("subfolder", comp.folder)
    if subgroup:
        parts.append(safe_component(subgroup))
    return Path(*parts, safe_component(name) + ".setting"), name
