"""Utensilios compartidos por las pruebas.

Construyen contenedores de prueba con el mismo formato interno que usa el
motor, para poder comprobar la lectura, la selección y el empaquetado sin
depender de Resolve ni de archivos privados.
"""

from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

GRAFO_VALIDO = """{
  Template = TextPlus { Inputs = { StyledText = Input { Value = "Hola", },
    Font = Input { Value = "Fuente de prueba", },
    Size = Input { Expression = "iif(time > 4, .1, .2)", }, },
    UserControls = ordered() { MiColor = { INPID_InputControl = "ColorControl", }, }, },
  MediaOut1 = MediaOut { Inputs = { Input = Input { SourceOp = "Template", Source = "Output", }, }, },
}"""

GRAFO_DOS_TEXTOS = """{
  TextoA = TextPlus { Inputs = { StyledText = Input { Value = "A", }, }, },
  TextoB = TextPlus { Inputs = { StyledText = Input { Value = "B", }, }, },
  MediaOut1 = MediaOut { Inputs = { Input = Input { SourceOp = "TextoA", Source = "Output", }, }, },
}"""

GRAFO_CON_MEDIOS = """{
  Template = TextPlus { Inputs = { StyledText = Input { Value = "Hola", }, }, },
  Imagen = Loader { Clips = {}, },
  MediaOut1 = MediaOut { Inputs = { Input = Input { SourceOp = "Template", Source = "Output", }, }, },
}"""


def composition_ba(herramientas: str) -> str:
    """Construye el valor hexadecimal de CompositionBA para un grafo dado."""
    cabecera = "Composition { Tools = ordered() { }, Compressed = true, }"
    cuerpo = zlib_compress(herramientas.encode("utf-8"))
    crudo = cabecera.encode("utf-8") + b"\x00" + struct.pack("<I", len(cuerpo)) + cuerpo
    return (b"\x00\x00\x00\x00" + zlib_compress(crudo)).hex()


def zlib_compress(datos: bytes) -> bytes:
    return zlib.compress(datos)


def _mp_folder_xml(carpeta: str, generadores: list[tuple[str, list[str]]]) -> str:
    partes = [f"<MpFolder><Name>{carpeta}</Name><MediaVec>"]
    for nombre, composiciones in generadores:
        partes.append("<Element><Sm2MpGenerator>")
        partes.append(f"<Name>{nombre}</Name>")
        for blob in composiciones:
            partes.append(f"<CompositionBA>{blob}</CompositionBA>")
        partes.append("</Sm2MpGenerator></Element>")
    partes.append("</MediaVec></MpFolder>")
    return "".join(partes)


def crear_drb(ruta: Path, carpetas: dict[str, list[tuple[str, list[str]]]]) -> Path:
    """Crea una bandeja .drb de prueba.

    ``carpetas`` relaciona el nombre de cada carpeta con la lista de
    generadores; cada generador indica su nombre y sus CompositionBA.
    """
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as archivo:
        for indice, (carpeta, generadores) in enumerate(carpetas.items(), start=1):
            # Cada carpeta es un MpFolder.xml, como en la bandeja real.
            archivo.writestr(f"Carpeta{indice}/MpFolder.xml", _mp_folder_xml(carpeta, generadores))
    return ruta


def crear_comp(ruta: Path, grafo: str = GRAFO_VALIDO) -> Path:
    """Crea un archivo .comp con un grafo de prueba."""
    ruta.write_text("Composition { Tools = ordered() " + grafo + " }", encoding="utf-8")
    return ruta
