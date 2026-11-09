"""Reglas de nombres, previsualización y destino.

Traduce las decisiones de la interfaz al formato de reglas del motor y calcula
qué se escribiría, dónde, sin escribir nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errores import ExportError
from .inventario import ComposicionInfo
from .modelo import Composition
from .nombres import title_destination

CARACTERES_INVALIDOS = '<>:"/\\|?*'


@dataclass
class OpcionesNombres:
    """Valores generales de atribución y nombre de los títulos exportados."""

    creador: str = ""
    coleccion: str = ""
    credito: str = ""
    prefijo: str = ""
    quitar_prefijo: str = ""
    guiones_a_espacios: bool = False
    mayusculas_iniciales: bool = False
    permitir_medios_externos: bool = False


@dataclass
class ReglaCarpeta:
    """Ajuste por carpeta de origen. Un campo vacío hereda el valor general."""

    carpeta: str
    creador: str = ""
    coleccion: str = ""
    credito: str = ""
    prefijo: str = ""
    quitar_prefijo: str = ""
    guiones_a_espacios: bool | None = None
    mayusculas_iniciales: bool | None = None
    subcarpeta: str = ""
    sin_subcarpeta: bool = False

    def vacia(self) -> bool:
        return not (self.creador or self.coleccion or self.credito or self.prefijo
                    or self.quitar_prefijo or self.subcarpeta or self.sin_subcarpeta
                    or self.guiones_a_espacios is not None
                    or self.mayusculas_iniciales is not None)

    def resumen(self) -> str:
        partes = []
        if self.creador:
            partes.append(f"creador: {self.creador}")
        if self.coleccion:
            partes.append(f"colección: {self.coleccion}")
        if self.credito:
            partes.append(f"crédito: {self.credito}")
        if self.subcarpeta:
            partes.append(f"subcarpeta: {self.subcarpeta}")
        if self.sin_subcarpeta:
            partes.append("sin subcarpeta")
        return " · ".join(partes) if partes else "Sin ajustes propios"


def construir_config(opciones: OpcionesNombres, reglas: Iterable[ReglaCarpeta]) -> dict:
    """Traduce las opciones de la interfaz al formato de reglas del motor."""
    defaults: dict = {
        "creator": opciones.creador.strip() or "Sin atribuir",
        "collection": opciones.coleccion.strip() or "Títulos exportados",
    }
    if opciones.credito.strip():
        defaults["credit"] = opciones.credito.strip()
    if opciones.prefijo.strip():
        defaults["prefix"] = opciones.prefijo.strip()
    if opciones.quitar_prefijo.strip():
        defaults["strip_prefix"] = opciones.quitar_prefijo.strip()
    if opciones.guiones_a_espacios:
        defaults["replace_hyphens"] = True
    if opciones.mayusculas_iniciales:
        defaults["title_case"] = True
    lista_reglas = []
    for regla in reglas:
        if regla.vacia():
            continue
        item: dict = {"folder": regla.carpeta}
        if regla.creador.strip():
            item["creator"] = regla.creador.strip()
        if regla.coleccion.strip():
            item["collection"] = regla.coleccion.strip()
        if regla.credito.strip():
            item["credit"] = regla.credito.strip()
        if regla.prefijo.strip():
            item["prefix"] = regla.prefijo.strip()
        if regla.quitar_prefijo.strip():
            item["strip_prefix"] = regla.quitar_prefijo.strip()
        if regla.guiones_a_espacios is not None:
            item["replace_hyphens"] = regla.guiones_a_espacios
        if regla.mayusculas_iniciales is not None:
            item["title_case"] = regla.mayusculas_iniciales
        if regla.sin_subcarpeta:
            item["subfolder"] = None
        elif regla.subcarpeta.strip():
            item["subfolder"] = regla.subcarpeta.strip()
        lista_reglas.append(item)
    return {"defaults": defaults, "rules": lista_reglas}


@dataclass
class Previsualizacion:
    """Nombre y ruta final de un título, con su error si no se puede calcular."""

    carpeta: str
    nombre: str
    ruta: str
    error: str = ""


def previsualizar(composiciones: Iterable[ComposicionInfo], config: dict) -> list[Previsualizacion]:
    """Calcula el nombre y la carpeta de salida de cada título seleccionado."""
    resultado = []
    for info in composiciones:
        simulado = Composition(info.carpeta, info.nombre, info.origen, "", "")
        try:
            relativa, nombre = title_destination(simulado, config)
        except ExportError as exc:
            resultado.append(Previsualizacion(info.carpeta, info.nombre, "", str(exc)))
            continue
        resultado.append(Previsualizacion(info.carpeta, nombre, relativa.as_posix()))
    return resultado


def rutas_en_conflicto(previsiones: Iterable[Previsualizacion]) -> list[tuple[str, list[str]]]:
    """Rutas que se repetirían en la misma carpeta, con los títulos implicados."""
    agrupadas: dict[str, list[str]] = {}
    for prevision in previsiones:
        if prevision.error or not prevision.ruta:
            continue
        clave = prevision.ruta.casefold()
        agrupadas.setdefault(clave, []).append(f"{prevision.carpeta}/{prevision.nombre}")
    return [(ruta, titulos) for ruta, titulos in agrupadas.items() if len(titulos) > 1]


def nombre_valido(nombre: str) -> bool:
    """Comprueba que un nombre de carpeta o archivo sea usable en Windows."""
    if not nombre or nombre.strip(" .") != nombre:
        return False
    if any(cara in CARACTERES_INVALIDOS for cara in nombre):
        return False
    return not any(ord(cara) < 32 for cara in nombre)


def comprobar_destino(carpeta_padre: Path | None, nombre_carpeta: str) -> tuple[Path | None, list[str]]:
    """Valida la carpeta de destino: debe ser nueva y su nombre, utilizable."""
    problemas: list[str] = []
    if carpeta_padre is None:
        return None, ["Elige una carpeta donde crear la exportación."]
    nombre = nombre_carpeta.strip()
    if not nombre:
        return None, ["Escribe el nombre de la carpeta nueva."]
    if not nombre_valido(nombre):
        return None, ["El nombre de la carpeta no es válido en Windows. Evita / \\ : * ? \" < > |."]
    if not carpeta_padre.is_dir():
        return None, ["La carpeta de destino no existe."]
    destino = carpeta_padre / nombre
    if destino.exists():
        problemas.append(f"Ya existe «{nombre}». Elige otro nombre: no se sobrescribe nada.")
    return destino, problemas


def comprobar_salida_paquete(carpeta_padre: Path | None, nombre: str) -> tuple[Path | None, list[str]]:
    """Valida el archivo .drfx de salida: debe ser nuevo y terminar en .drfx."""
    problemas: list[str] = []
    if carpeta_padre is None:
        return None, ["Elige una carpeta donde guardar el paquete."]
    limpio = nombre.strip()
    if not limpio:
        return None, ["Escribe el nombre del paquete."]
    if not limpio.lower().endswith(".drfx"):
        limpio += ".drfx"
    if not nombre_valido(limpio):
        return None, ["El nombre del paquete no es válido en Windows."]
    salida = carpeta_padre / limpio
    if salida.exists():
        problemas.append(f"Ya existe «{salida.name}». Elige otro nombre: no se sobrescribe nada.")
    return salida, problemas
