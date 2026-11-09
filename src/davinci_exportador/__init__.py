"""DaVinci Exportador: convierte composiciones Fusion en plantillas de Resolve.

El motor no depende de ninguna interfaz: se puede usar como biblioteca, desde
la línea de comandos o desde la app de escritorio.
"""

from __future__ import annotations

from .conversion import VERSION, export_titles, make_title
from .empaquetado import inspect_templates, package_templates
from .errores import ExportError
from .inventario import ComposicionInfo, Inventario, inventariar
from .lectura import read_compositions, read_compositions_report
from .modelo import Composition, Lectura, Node
from .nombres import safe_component, title_destination

__version__ = VERSION

__all__ = [
    "VERSION",
    "ComposicionInfo",
    "Composition",
    "ExportError",
    "Inventario",
    "Lectura",
    "Node",
    "__version__",
    "export_titles",
    "inspect_templates",
    "inventariar",
    "make_title",
    "package_templates",
    "read_compositions",
    "read_compositions_report",
    "safe_component",
    "title_destination",
]
