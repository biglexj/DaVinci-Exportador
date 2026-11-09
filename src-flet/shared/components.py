"""Componentes visuales compartidos por las dos operaciones.

Piezas pequeñas y neutras que las dos operaciones comparten: encabezado de
paso, bloques de mensaje y contenedores de superficie. No contienen lógica de
exportación.
"""

from __future__ import annotations

import flet as ft

from app.tema import COLOR_AVISO, COLOR_BORDE, COLOR_ERROR, COLOR_OK, COLOR_TENUE, RADIO


def paso(numero: int, titulo: str, ayuda: str = "") -> ft.Column:
    """Encabezado numerado de un paso del recorrido."""
    numero_control = ft.Container(
        content=ft.Text(str(numero), size=13, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_PRIMARY),
        bgcolor=ft.Colors.PRIMARY,
        width=24, height=24, border_radius=12,
        alignment=ft.Alignment.CENTER,
    )
    textos = [ft.Text(titulo, size=16, weight=ft.FontWeight.W_600)]
    if ayuda:
        textos.append(ft.Text(ayuda, size=12, color=COLOR_TENUE))
    return ft.Column(
        controls=[
            ft.Row(
                controls=[numero_control, ft.Column(controls=textos, spacing=2, expand=True)],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ],
        spacing=4,
    )


def mensaje(texto: str, pista: str = "", tono: str = "error") -> ft.Container:
    """Bloque de mensaje con una pista de resolución."""
    color = {"error": COLOR_ERROR, "aviso": COLOR_AVISO, "ok": COLOR_OK}.get(tono, COLOR_TENUE)
    controles = [ft.Text(texto, size=13, color=color)]
    if pista:
        controles.append(ft.Text(pista, size=12, color=COLOR_TENUE))
    return ft.Container(
        content=ft.Column(controls=controles, spacing=2),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border_radius=RADIO,
        border=ft.Border(left=ft.BorderSide(3, color)),
    )


def superficie(contenido: ft.Control, padding: int = 12) -> ft.Container:
    """Contenedor de superficie neutra para agrupar contenido."""
    return ft.Container(
        content=contenido,
        padding=ft.Padding.symmetric(horizontal=padding, vertical=padding),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border_radius=RADIO,
        border=ft.Border.all(1, COLOR_BORDE),
    )


def separador() -> ft.Divider:
    return ft.Divider(height=1, color=COLOR_BORDE, opacity=0.6)


def ruta_texto(valor: str) -> ft.Text:
    """Texto de ruta legible, con salto de línea para no recortarse."""
    return ft.Text(valor, size=12, color=COLOR_TENUE, selectable=True)


def boton_accion(contenido: str, icono, al_pulsar) -> ft.Button:
    """Botón principal, ancho y destacado."""
    return ft.Button(
        content=contenido,
        icon=icono,
        on_click=al_pulsar,
        height=44,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
    )


def refrescar(control) -> None:
    """Actualiza un control si ya está montado; ignora los que aún no lo están."""
    if control is None:
        return
    try:
        if getattr(control, "page", None) is not None:
            control.update()
    except RuntimeError:
        pass
