"""Conversión de composiciones Fusion en títulos .setting.

Publica los controles básicos de texto y los controles personalizados del
TextPlus; conserva los nodos interiores y sus animaciones. No normaliza
tiempos, resolución ni estilos, y no ejecuta el código Lua de la plantilla.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
from pathlib import Path

from .errores import ExportError
from .fusion import entries, find_table, quoted
from .lectura import read_compositions
from .modelo import Composition
from .nombres import title_destination
from .utiles import file_sha256, renombrar_con_reintentos

VERSION = "0.2.0"
STANDARD_INPUTS = (
    "StyledText", "Font", "Style", "Size", "Center", "Pivot", "Angle",
    "CharacterSpacing", "LineSpacing", "Red1", "Green1", "Blue1", "Alpha1",
    "ShadingMappingSize1",
)


def make_title(comp: Composition) -> tuple[str, dict]:
    """Convierte una composición en el texto de un título .setting."""
    nodes = entries(comp.tools)
    text_nodes = [node for node in nodes if node.kind == "TextPlus"]
    outputs = [node for node in nodes if node.kind == "MediaOut"]
    if len(text_nodes) != 1 or len(outputs) != 1:
        raise ExportError(f"{comp.folder}/{comp.name}: requiere un TextPlus y un MediaOut raíz; no se elige uno arbitrariamente.")
    primary = text_nodes[0]
    output_input = find_table(outputs[0].text, "Inputs")
    connection = next((node for node in entries(output_input) if node.name == "Input"), None)
    if connection is None:
        raise ExportError(f"{comp.name}: MediaOut no tiene entrada conectada.")
    op = re.search(r'\bSourceOp\s*=\s*"([^"\n]+)"', connection.text)
    port = re.search(r'\bSource\s*=\s*"([^"\n]+)"', connection.text)
    if not op or not port or op[1] not in {node.name for node in nodes}:
        raise ExportError(f"{comp.name}: conexión de salida incompleta.")
    custom = []
    if re.search(r"\bUserControls\s*=", primary.text):
        custom = [node.name for node in entries(find_table(primary.text, "UserControls"), typed=False)]
    controls = list(dict.fromkeys([*STANDARD_INPUTS, *custom]))
    inputs = []
    for name in controls:
        key = name if re.fullmatch(r"\w+", name) else "[" + quoted(name) + "]"
        label = ', Name = "Texto"' if name == "StyledText" else ""
        inputs.append(f"{key} = InstanceInput {{ SourceOp = {quoted(primary.name)}, Source = {quoted(name)}{label}, }},")
    graph = ",\n".join(node.text for node in nodes if node.kind != "MediaOut")
    # Las declaraciones de los nodos se copian literalmente. No se ejecutan sus
    # expresiones, botones, scripts ni referencias a archivos durante la conversión.
    setting = (
        '{\nTools = ordered() {\nExportedTitle = MacroOperator {\nNameSet = true,\n'
        'Inputs = ordered() {\n' + "\n".join(inputs) + '\n},\n'
        'Outputs = { MainOutput1 = InstanceOutput { SourceOp = ' + quoted(op[1]) + ', Source = ' + quoted(port[1]) + ', }, },\n'
        'ViewInfo = GroupInfo { Pos = { 0, 0 } },\nTools = ordered() {\n' + graph + '\n},\n},\n},\nActiveTool = "ExportedTitle",\n}\n'
    )
    metadata = {
        "fonts": sorted(set(re.findall(r'Font\s*=\s*Input\s*\{\s*Value\s*=\s*"([^"\n]+)"', comp.tools))),
        "external_media_nodes": [node.name for node in nodes if node.kind in {"Loader", "MediaIn", "uLoader", "FBXMesh3D"}],
        "controls": controls,
        "node_count": len(nodes) - 1,
    }
    return setting, metadata


def export_titles(source: Path, output: Path, folders: list[str] | None = None,
                  config: dict | None = None, allow_external: bool = False,
                  progreso=None, seleccion: set[tuple[str, str]] | None = None) -> dict:
    """Convierte composiciones compatibles en una carpeta nueva de plantillas.

    ``progreso`` recibe ``(hechos, total, mensaje)`` con datos reales de avance.
    ``seleccion`` limita la exportación a los pares ``(carpeta, nombre)`` indicados.
    """
    output = output.resolve()
    if output.exists():
        raise ExportError("La carpeta de salida ya existe; no se sobrescribe ni mezcla contenido.")
    compositions = read_compositions(source)
    if folders:
        missing = set(folders) - {comp.folder for comp in compositions}
        if missing:
            raise ExportError("Carpetas sin composiciones: " + ", ".join(sorted(missing)))
        compositions = [comp for comp in compositions if comp.folder in folders]
    if seleccion is not None:
        compositions = [comp for comp in compositions if (comp.folder, comp.name) in seleccion]
        if not compositions:
            raise ExportError("No hay títulos seleccionados para exportar.")
    planned, reserved = [], set()
    for comp in compositions:
        text, metadata = make_title(comp)
        if metadata["external_media_nodes"] and not allow_external:
            raise ExportError(f"{comp.name}: depende de medios externos; revisar antes de usar --permitir-medios-externos.")
        relative, name = title_destination(comp, config or {})
        key = relative.as_posix().casefold()
        if key in reserved:
            raise ExportError(f"Dos títulos producirían la misma ruta: {relative}. Ajustar las reglas de nombres.")
        reserved.add(key)
        planned.append((comp, relative, name, text, metadata))
    if not planned:
        raise ExportError("No hay títulos compatibles para exportar.")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Se publica una carpeta completa solo cuando todos los títulos son válidos.
    stage = Path(tempfile.mkdtemp(prefix=".exportador-", dir=output.parent)).resolve()
    try:
        manifest = []
        for index, (comp, relative, name, text, metadata) in enumerate(planned, start=1):
            destination = stage / "Templates" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
            manifest.append({"source_folder": comp.folder, "source_name": comp.name,
                             "source_member": comp.source, "title": name,
                             "relative": relative.as_posix(),
                             "sha256": file_sha256(destination), **metadata})
            if progreso:
                progreso(index, len(planned), comp.name)
        report = {"exporter_version": VERSION, "source": str(source.resolve()),
                  "source_sha256": file_sha256(source),
                  "titles": manifest, "native_render_verified": False,
                  "note": "Conversión sin Resolve; no comprueba fuentes instaladas, botones ni render."}
        (stage / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        with (stage / "titulos.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Carpeta original", "Nombre original", "Título exportado", "Ruta", "SHA256"])
            for item in manifest:
                writer.writerow([item["source_folder"], item["source_name"], item["title"], item["relative"], item["sha256"]])
        if stage.parent != output.parent or output.exists():
            raise ExportError("El destino cambió durante la exportación; se cancela.")
        renombrar_con_reintentos(stage, output)
    finally:
        # Solo se retira el temporal creado por esta operación en el padre elegido.
        if stage.exists() and stage.parent == output.parent and stage.name.startswith(".exportador-"):
            shutil.rmtree(stage)
    return {"titles": len(planned), "output": str(output)}
