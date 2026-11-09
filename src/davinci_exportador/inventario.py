"""Inventario de las composiciones de un origen.

Dice qué se puede exportar y por qué lo demás no. No depende de la interfaz:
la usan tanto la app de escritorio como la línea de comandos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .conversion import make_title
from .errores import ExportError
from .lectura import read_compositions_report


@dataclass(frozen=True)
class ComposicionInfo:
    """Una composición del origen, con su compatibilidad y sus pendientes."""

    carpeta: str
    nombre: str
    origen: str
    compatible: bool
    motivo: str = ""
    fuentes: tuple[str, ...] = ()
    medios: tuple[str, ...] = ()

    @property
    def clave(self) -> tuple[str, str]:
        return (self.carpeta, self.nombre)

    @property
    def necesita_medios(self) -> bool:
        return bool(self.medios)


@dataclass
class Inventario:
    """Resultado de inspeccionar un origen, con o sin errores."""

    origen: Path | None = None
    composiciones: list[ComposicionInfo] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def carpetas(self) -> list[str]:
        return list(dict.fromkeys(comp.carpeta for comp in self.composiciones))

    @property
    def compatibles(self) -> list[ComposicionInfo]:
        return [comp for comp in self.composiciones if comp.compatible]

    @property
    def hay_contenido(self) -> bool:
        return bool(self.composiciones)


def inventariar(origen: Path) -> Inventario:
    """Lee el origen y explica, título a título, qué se puede exportar."""
    try:
        lectura = read_compositions_report(origen)
    except (ExportError, OSError) as exc:
        return Inventario(origen=origen, error=str(exc))
    composiciones: list[ComposicionInfo] = []
    for comp in lectura.compositions:
        try:
            _texto, metadata = make_title(comp)
        except ExportError as exc:
            composiciones.append(ComposicionInfo(comp.folder, comp.name, comp.source, False, str(exc)))
            continue
        composiciones.append(ComposicionInfo(
            comp.folder, comp.name, comp.source, True, "",
            tuple(metadata.get("fonts", ())),
            tuple(metadata.get("external_media_nodes", ())),
        ))
    return Inventario(origen=origen, composiciones=composiciones, problemas=list(lectura.problems))
