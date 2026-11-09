"""Lector del formato interno de Fusion.

Resolve guarda las composiciones en un formato propietario: tablas Lua
comprimidas. Aquí se leen sin ejecutar nada: ni Lua, ni expresiones, ni
botones. Un formato que no se entiende se rechaza en lugar de adivinarlo.
"""

from __future__ import annotations

import json
import re
import zlib

from .errores import ExportError
from .modelo import Node

MAX_COMPOSITION_BYTES = 64 * 1024 * 1024
LUA_KEY = r'(?:\w+|\["(?:[^"\\]|\\.)*"\])'


def quoted(value: str) -> str:
    """Cita un valor como cadena Lua."""
    return json.dumps(value, ensure_ascii=False)


def table_end(text: str, start: int) -> int:
    """Localiza el cierre de una tabla Lua sin ejecutar su contenido."""
    if start >= len(text) or text[start] != "{":
        raise ExportError("No se encontró el inicio de una tabla Fusion.")
    depth, i = 0, start
    while i < len(text):
        comment = text.startswith("--", i)
        offset = i + 2 if comment else i
        long_string = re.match(r"\[(=*)\[", text[offset:])
        if long_string:
            close = "]" + long_string[1] + "]"
            end = text.find(close, offset + long_string.end())
            if end < 0:
                raise ExportError("Cadena larga Lua sin cerrar.")
            i = end + len(close)
            continue
        if comment:
            end = text.find("\n", i)
            i = len(text) if end < 0 else end + 1
            continue
        if text[i] in "\"'":
            delimiter = text[i]
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == delimiter:
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise ExportError("Cadena Lua sin cerrar.")
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ExportError("Tabla Lua sin cerrar.")


def decode_key(key: str) -> str:
    """Lee una clave de tabla Lua, incluida la forma entre corchetes."""
    if not key.startswith("["):
        return key
    try:
        return json.loads(key[1:-1])
    except json.JSONDecodeError as exc:
        raise ExportError(f"Identificador Lua no soportado: {key}") from exc


def entries(table: str, typed: bool = True) -> list[Node]:
    """Lee entradas del nivel inmediato; conserva cada declaración original."""
    start = table.index("{")
    end = table_end(table, start)
    position, nodes = start + 1, []
    kind_pattern = r"([\w.]+)(?:\(\))?\s*" if typed else ""
    pattern = re.compile(r"(" + LUA_KEY + r")\s*=\s*" + kind_pattern + r"\{")
    while position < end - 1:
        while position < end - 1 and (table[position].isspace() or table[position] == ","):
            position += 1
        if position >= end - 1:
            break
        match = pattern.match(table, position)
        if not match:
            raise ExportError(f"Entrada Fusion no soportada: {table[position:position + 70]}")
        close = table_end(table, match.end() - 1)
        nodes.append(Node(decode_key(match[1]), match[2] if typed else "", table[position:close]))
        position = close
    return nodes


def find_table(text: str, key: str) -> str:
    """Devuelve la tabla que sigue a ``key =`` dentro de un texto Fusion."""
    match = re.search(r"\b" + re.escape(key) + r"\s*=\s*(?:ordered\(\)\s*)?\{", text)
    if not match:
        raise ExportError(f"No se encontró la tabla {key}.")
    start = match.end() - 1
    return text[start:table_end(text, start)]


def limited_inflate(data: bytes) -> bytes:
    """Descomprime con un límite de memoria y exige que el flujo esté completo."""
    inflater = zlib.decompressobj()
    try:
        result = inflater.decompress(data, MAX_COMPOSITION_BYTES + 1)
    except zlib.error as exc:
        raise ExportError("Composición comprimida inválida.") from exc
    if len(result) > MAX_COMPOSITION_BYTES or not inflater.eof:
        raise ExportError("Composición incompleta o superior al límite de 64 MiB.")
    return result


def decode_composition(blob: str) -> tuple[str, str]:
    """Lee CompositionBA de DRB/DRP; rechaza representaciones desconocidas.

    El contenedor es interno de Resolve y puede cambiar entre versiones.
    No reescribe ese contenedor ni intenta fabricar proyectos DRP.
    """
    try:
        raw = limited_inflate(bytes.fromhex(blob)[4:])
    except ValueError as exc:
        raise ExportError("CompositionBA no contiene datos hexadecimales válidos.") from exc
    start = raw.find(b"Composition {")
    if start < 0:
        raise ExportError("No se encontró Composition en CompositionBA.")
    # Latin-1 conserva los offsets de bytes para separar cabecera y bloque binario.
    view = raw[start:].decode("latin-1")
    end = start + table_end(view, view.index("{"))
    header = raw[start:end].decode("utf-8")
    if re.search(r"\bCompressed\s*=\s*true\b", header):
        # Fusion: NUL, longitud de cuatro bytes y flujo zlib.
        tools = limited_inflate(raw[end + 5:]).rstrip(b"\x00").decode("utf-8")
        entries(tools)
        text = re.sub(r"\bCompressed\s*=\s*true\s*,?", lambda _: "Tools = ordered() " + tools + ",", header, count=1)
        return text, tools
    return header, find_table(header, "Tools")
