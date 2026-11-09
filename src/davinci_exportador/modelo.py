"""Estructuras de datos que atraviesan el exportador."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    """Un nodo del grafo Fusion y su declaración original."""

    name: str
    kind: str
    text: str


@dataclass(frozen=True)
class Composition:
    """Una composición leída de un archivo de origen."""

    folder: str
    name: str
    source: str
    text: str
    tools: str


@dataclass(frozen=True)
class Lectura:
    """Composiciones leídas y problemas encontrados por entrada.

    Los problemas son de una composición concreta y no impiden leer el resto.
    """

    compositions: list[Composition]
    problems: list[str]
