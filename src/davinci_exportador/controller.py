"""Operaciones de alto nivel: exportar y empaquetar.

Es la capa que consume la interfaz: valida, ejecuta con progreso real y
devuelve un resultado legible, con la ubicación de lo generado.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .conversion import export_titles
from .empaquetado import inspect_templates, package_templates
from .errores import ExportError

Progreso = Callable[[int, int, str], None]


def _historial_archivo() -> Path:
    return Path.home() / ".davinci_exportador" / "historial_paquetes.json"


def obtener_historial_paquetes() -> list[dict]:
    """Carga el historial de paquetes creados recientemente."""
    archivo = _historial_archivo()
    if not archivo.is_file():
        return []
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        if isinstance(datos, list):
            return datos
    except Exception:
        pass
    return []


def guardar_en_historial(entrada: dict) -> None:
    """Registra una creación en el historial de paquetes (hasta 30 entradas)."""
    try:
        archivo = _historial_archivo()
        archivo.parent.mkdir(parents=True, exist_ok=True)
        historial = obtener_historial_paquetes()
        historial = [h for h in historial if h.get("paquete") != entrada.get("paquete")]
        historial.insert(0, entrada)
        historial = historial[:30]
        archivo.write_text(json.dumps(historial, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


@dataclass
class ResultadoExportacion:
    """Lo que se ha generado y dónde está."""

    carpeta: Path
    titulos: int
    manifiesto: dict
    avisos: list[str] = field(default_factory=list)

    @property
    def fuentes(self) -> list[str]:
        fuentes: set[str] = set()
        for titulo in self.manifiesto.get("titles", []):
            fuentes.update(titulo.get("fonts", []))
        return sorted(fuentes)

    @property
    def medios(self) -> list[str]:
        medios: set[str] = set()
        for titulo in self.manifiesto.get("titles", []):
            medios.update(titulo.get("external_media_nodes", []))
        return sorted(medios)

    @property
    def ruta_manifiesto(self) -> Path:
        return self.carpeta / "manifest.json"


@dataclass
class ResultadoPaquete:
    """Resumen de un .drfx recién creado."""

    paquete: Path
    archivos: int
    titulos: int
    sha256: str
    metadata: dict = field(default_factory=dict)


def exportar_titulos(origen: Path, destino: Path, seleccion: set[tuple[str, str]], config: dict,
                     permitir_medios: bool = False, progreso: Progreso | None = None) -> ResultadoExportacion:
    """Exporta los títulos indicados a una carpeta nueva."""
    export_titles(origen, destino, config=config, allow_external=permitir_medios,
                  progreso=progreso, seleccion=seleccion)
    manifiesto = json.loads((destino / "manifest.json").read_text(encoding="utf-8"))
    return ResultadoExportacion(destino, len(manifiesto.get("titles", [])), manifiesto)


def comprobar_plantillas(carpeta: Path | None) -> tuple[dict | None, str | None]:
    """Comprueba la estructura de una carpeta de plantillas sin escribir nada."""
    if carpeta is None:
        return None, "Elige una carpeta de plantillas."
    if not carpeta.exists():
        return None, "La carpeta indicada no existe."
    if not carpeta.is_dir():
        return None, "La ruta indicada no es una carpeta."
    try:
        return inspect_templates(carpeta), None
    except (ExportError, OSError) as exc:
        return None, str(exc)


def empaquetar_plantillas(carpeta: Path, salida: Path, progreso: Progreso | None = None,
                          metadata: dict | None = None) -> ResultadoPaquete:
    """Crea el paquete .drfx, registra en historial y devuelve su resumen."""
    resultado = package_templates(carpeta, salida, progreso=progreso, metadata=metadata)
    meta = metadata or {}
    resultado_obj = ResultadoPaquete(
        Path(resultado["package"]),
        resultado["files"],
        resultado["settings"],
        resultado["sha256"],
        metadata=meta,
    )
    guardar_en_historial({
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "paquete": str(resultado_obj.paquete),
        "nombre": resultado_obj.paquete.name,
        "carpeta_origen": str(carpeta),
        "archivos": resultado_obj.archivos,
        "titulos": resultado_obj.titulos,
        "sha256": resultado_obj.sha256,
        "autor": meta.get("author", "Biglex J"),
        "version": meta.get("version", "1.0.0"),
    })
    return resultado_obj


def explicar_error(exc: Exception) -> tuple[str, str]:
    """Traduce un error del motor a un mensaje comprensible y una pista."""
    mensaje = str(exc) or exc.__class__.__name__
    minusculas = mensaje.lower()
    pista = ""
    if "ya existe" in minusculas:
        pista = "Elige un nombre que todavía no exista: no se sobrescribe nada."
    elif "no se encontraron composiciones" in minusculas:
        pista = "Exporta desde Resolve la bandeja (DRB) o el proyecto (DRP) que contiene los títulos."
    elif "medios externos" in minusculas:
        pista = ("Si el título usa esos medios a propósito, activa «Permitir medios externos» "
                 "en las opciones avanzadas. No se incrustan ni se resuelven rutas.")
    elif "misma ruta" in minusculas:
        pista = "Cambia el creador, la colección o el nombre para que no coincidan."
    elif "entrada admitida" in minusculas:
        pista = "Los archivos admitidos son .drb, .drp, .comp y .setting."
    elif "no se pudo leer el contenedor" in minusculas:
        pista = "El archivo puede estar dañado o no ser una bandeja exportada de Resolve."
    elif "extensión .drfx" in minusculas:
        pista = "El paquete debe terminar en .drfx."
    elif "no hay archivos .setting" in minusculas:
        pista = "La carpeta debe contener Edit/Titles con archivos .setting."
    elif "ruta inválida" in minusculas:
        pista = ("Usa la carpeta que contiene Edit/Titles, Edit/Effects, "
                 "Edit/Generators o Edit/Transitions.")
    elif "textplus" in minusculas:
        pista = "El título necesita un único TextPlus y un MediaOut en el nivel raíz."
    elif "composition" in minusculas or "composición" in minusculas:
        pista = "El archivo usa un formato interno de Resolve que esta versión no reconoce."
    return mensaje, pista


def abrir_en_el_sistema(ruta: Path) -> None:
    """Abre una carpeta o un archivo con la aplicación del sistema."""
    objetivo = str(ruta)
    if sys.platform == "win32":
        os.startfile(objetivo)  # noqa: S606 - acción del sistema solicitada por la persona
    else:
        subprocess.Popen(["xdg-open", objetivo])
