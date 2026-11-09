"""Carcasa de la aplicación.

Une las dos operaciones bajo un único encabezado y un único selector de modo.
No contiene lógica de exportación: solo decide qué vista se muestra.
"""

from __future__ import annotations

import sys
from pathlib import Path

import flet as ft

from app.tema import COLOR_TENUE, TEMA
from features.empaquetar.empaquetar_view import VistaEmpaquetar
from features.exportar.exportar_view import VistaExportarTitulos

MODO_EXPORTAR = "exportar"
MODO_EMPAQUETAR = "empaquetar"

BRANDING = Path(__file__).resolve().parents[2] / "assets" / "branding" / "icons"

VISTAS: tuple[VistaExportarTitulos, VistaEmpaquetar] | None = None


def ruta_icono() -> str | None:
    """Ruta del icono de la ventana, o None si no está disponible.

    En el ejecutable compilado los recursos viven junto al paquete congelado;
    en modo fuente, en `assets/branding/icons`.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        candidato = base / "assets" / "branding" / "icons" / "icon-windows.ico"
    else:
        candidato = BRANDING / "icon-windows.ico"
    return str(candidato) if candidato.is_file() else None


def cambiar_modo(vista_exportar: VistaExportarTitulos, vista_empaquetar: VistaEmpaquetar,
                 seleccionado: str) -> None:
    """Deja visible la vista del modo elegido."""
    vista_exportar.raiz.visible = seleccionado == MODO_EXPORTAR
    vista_empaquetar.raiz.visible = seleccionado == MODO_EMPAQUETAR
    vista_exportar.raiz.update()
    vista_empaquetar.raiz.update()


def construir(page: ft.Page) -> tuple[VistaExportarTitulos, VistaEmpaquetar]:
    """Monta la ventana completa orientada a empaquetado de plantillas .drfx."""
    global VISTAS
    page.title = "DaVinci Template Packager"
    page.theme = TEMA
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0
    # La ventana es redimensionable y el contenido se adapta con ResponsiveRow:
    # con escalado de Windows alto, los campos pasan a una columna en lugar de recortarse.
    page.window.width = 1180
    page.window.height = 840
    page.window.min_width = 820
    page.window.min_height = 580
    page.window.bgcolor = ft.Colors.SURFACE_CONTAINER_LOWEST
    page.window.alignment = ft.Alignment(0, 0)
    page.window.visible = False
    icono = ruta_icono()
    if icono:
        page.window.icon = icono

    selector = ft.FilePicker()
    page.services.append(selector)

    vista_exportar = VistaExportarTitulos(page, selector)
    vista_empaquetar = VistaEmpaquetar(page, selector)
    vista_exportar.raiz.visible = False
    vista_empaquetar.raiz.visible = True

    cabecera = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.INVENTORY_2, size=20, color=ft.Colors.PRIMARY),
                ft.Text("DaVinci Template Packager", size=17, weight=ft.FontWeight.W_600),
                ft.Container(
                    content=ft.Text("DRFX Hub", size=11, color=ft.Colors.PRIMARY),
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    border_radius=6,
                ),
                ft.Container(expand=True),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
    )

    pie = ft.Container(
        content=ft.Text(
            "Empaquetador oficial de plantillas Fusion en formato .drfx para DaVinci Resolve. "
            "No sobrescribe destinos ni altera archivos originales.",
            size=11, color=COLOR_TENUE,
        ),
        padding=ft.Padding.symmetric(horizontal=20, vertical=8),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.Border(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
    )

    page.add(
        ft.SafeArea(
            content=ft.Column(
                controls=[
                    cabecera,
                    ft.Column(
                        controls=[vista_empaquetar.raiz],
                        spacing=0,
                        expand=True,
                    ),
                    pie,
                ],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )
    )
    VISTAS = (vista_exportar, vista_empaquetar)
    return VISTAS


async def main(page: ft.Page) -> None:
    construir(page)
    # Espera a que la ventana esté lista antes de centrarla y mostrarla,
    # evitando que arranque a la izquierda o parpadee.
    await page.window.wait_until_ready_to_show()
    await page.window.center()
    page.window.visible = True
    page.window.update()
    page.update()
    icono = ruta_icono()
    if icono:
        # En Flet 1.x el cliente de escritorio fuerza su propio icono en la barra
        # de título de Windows: el oficial se aplica al ejecutable y al
        # instalador, no a la ventana.
        page.window.icon = icono


def open_desktop() -> None:
    """Abre la ventana de escritorio de la app.

    En Flet 1.x el punto de entrada publico es `ft.run`; `ft.app` ya no es
    un atributo del paquete (passa a ser el modulo interno que lo implementa).
    """
    ft.run(main)
