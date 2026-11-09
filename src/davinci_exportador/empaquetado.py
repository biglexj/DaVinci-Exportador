"""Empaquetado de plantillas en un archivo .drfx.

El empaquetador incluye los recursos que ya estén en la carpeta seleccionada.
No descarga dependencias, no convierte rutas absolutas en relativas y no
instala el paquete en Resolve.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from .errores import ExportError
from .utiles import file_sha256, renombrar_con_reintentos

TEMPLATE_CATEGORIES = {"Titles", "Effects", "Generators", "Transitions"}


def _scan_templates(folder: Path) -> tuple[list[Path], list[Path]]:
    """Devuelve los archivos empaquetables y los .setting, validando la estructura."""
    files = []
    for item in sorted(folder.rglob("*")):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise ExportError("No se empaquetan enlaces o uniones: " + str(item))
        if item.is_file():
            files.append(item)
    settings = [item for item in files if item.suffix.lower() == ".setting"]
    if not settings:
        raise ExportError("No hay archivos .setting para empaquetar.")
    for item in settings:
        parts = item.relative_to(folder).parts
        if len(parts) < 3 or parts[0] != "Edit" or parts[1] not in TEMPLATE_CATEGORIES:
            raise ExportError("Usar la carpeta que contiene Edit/Titles, Edit/Effects, etc.; ruta inválida: " + str(item))
    return files, settings


def inspect_templates(folder: Path) -> dict:
    """Comprueba la estructura de una carpeta de plantillas y describe su contenido.

    No escribe nada. Describe lo que el empaquetador incluiría, recursos,
    categorías detectadas y el catálogo de plantillas .setting encontradas.
    """
    folder = folder.resolve(strict=True)
    if not folder.is_dir():
        raise ExportError("La carpeta indicada no existe o no es un directorio.")
    files, settings = _scan_templates(folder)
    categories = sorted({item.relative_to(folder).parts[1] for item in settings})

    categories_summary = {cat: 0 for cat in categories}
    templates = []
    for item in settings:
        rel = item.relative_to(folder)
        cat = rel.parts[1]
        categories_summary[cat] = categories_summary.get(cat, 0) + 1
        subfolder = "/".join(rel.parts[2:-1]) if len(rel.parts) > 3 else ""
        templates.append({
            "name": item.stem,
            "category": cat,
            "subfolder": subfolder,
            "relative": rel.as_posix(),
            "size_bytes": item.stat().st_size,
        })
    templates.sort(key=lambda t: (t["category"], t["relative"]))

    return {
        "folder": str(folder),
        "files": len(files),
        "settings": len(settings),
        "resources": len(files) - len(settings),
        "categories": categories,
        "categories_summary": categories_summary,
        "templates": templates,
    }


def package_templates(folder: Path, output: Path, progreso=None, metadata: dict | None = None) -> dict:
    """Crea un paquete .drfx. ``progreso`` recibe ``(hechos, total, mensaje)``."""
    folder, output = folder.resolve(strict=True), output.resolve()
    if not folder.is_dir() or output.suffix.lower() != ".drfx":
        raise ExportError("Indicar una carpeta de plantillas y una salida con extensión .drfx.")
    if output.exists():
        raise ExportError("El paquete de salida ya existe; no se sobrescribe.")
    files, settings = _scan_templates(folder)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=".drfx-", suffix=".tmp", dir=output.parent, delete=False)
    temporary = Path(handle.name).resolve()
    handle.close()
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for index, item in enumerate(files, start=1):
                archive.write(item, item.relative_to(folder).as_posix())
                if progreso:
                    progreso(index, len(files), item.name)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ExportError("El paquete no superó la comprobación de integridad.")
        if temporary.parent != output.parent or output.exists():
            raise ExportError("El destino cambió durante el empaquetado.")
        renombrar_con_reintentos(temporary, output)
    finally:
        if temporary.exists() and temporary.parent == output.parent:
            temporary.unlink()
    return {"files": len(files), "settings": len(settings), "package": str(output),
            "sha256": file_sha256(output), "metadata": metadata or {}}
