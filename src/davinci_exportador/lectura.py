"""Lectura de los archivos de origen.

Admite la bandeja exportada desde Resolve (.drb), un proyecto ya exportado
(.drp) y archivos de texto .comp o .setting. La lectura de DRP es
experimental: el formato es el mismo que en DRB, pero no se ha probado con
todos los tipos de proyecto.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .errores import ExportError
from .fusion import decode_composition, find_table
from .modelo import Composition, Lectura

MAX_XML_BYTES = 64 * 1024 * 1024

#: Extensiones de archivo que el motor sabe leer como origen.
EXTENSIONES_ENTRADA = (".drb", ".drp", ".comp", ".setting")


def read_compositions_report(source: Path) -> Lectura:
    """Lee las composiciones y anota los problemas de cada entrada.

    Una composición ilegible no oculta el resto del archivo. El contenedor es
    interno de Resolve y puede cambiar entre versiones: se rechaza lo que no
    se entiende en lugar de adivinarlo.
    """
    source = source.resolve(strict=True)
    if source.suffix.lower() in {".comp", ".setting"}:
        text = source.read_text(encoding="utf-8-sig")
        return Lectura([Composition(source.parent.name, source.stem, str(source), text, find_table(text, "Tools"))], [])
    if source.suffix.lower() not in EXTENSIONES_ENTRADA:
        raise ExportError("Entrada admitida: .drb, .drp, .comp o .setting.")
    result, problems = [], []
    try:
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                if not member.filename.endswith("MpFolder.xml"):
                    continue
                if member.file_size > MAX_XML_BYTES:
                    raise ExportError(f"XML demasiado grande: {member.filename}")
                xml = archive.read(member).decode("utf-8-sig")
                # Resolve escribe nombres de clase como ListMgt::LmVersionTable,
                # que no son etiquetas XML estándar. Solo se normaliza esa copia.
                xml = re.sub(r"(<\/?[\w]+)::", r"\1__", xml)
                try:
                    root = ET.fromstring(xml)
                except ET.ParseError as exc:
                    problems.append(f"{member.filename}: XML ilegible ({exc}).")
                    continue
                folder = root.findtext("Name", default="Sin carpeta")
                for generator in root.findall("./MediaVec/Element/Sm2MpGenerator"):
                    label = generator.findtext("Name", default="Sin nombre")
                    try:
                        blobs = generator.findall(".//CompositionBA")
                        if len(blobs) != 1:
                            raise ExportError("se requiere exactamente una composición.")
                        text, tools = decode_composition(blobs[0].text or "")
                    except ExportError as exc:
                        problems.append(f"{folder}/{label}: {exc}")
                        continue
                    result.append(Composition(folder, label, member.filename, text, tools))
    except (zipfile.BadZipFile, UnicodeError) as exc:
        raise ExportError(f"No se pudo leer el contenedor: {exc}") from exc
    return Lectura(result, problems)


def read_compositions(source: Path) -> list[Composition]:
    """Lee las composiciones del origen. Falla si alguna entrada es ilegible."""
    source = source.resolve(strict=True)
    lectura = read_compositions_report(source)
    if lectura.problems:
        raise ExportError(lectura.problems[0])
    if not lectura.compositions:
        raise ExportError("No se encontraron composiciones Fusion exportables.")
    return lectura.compositions
