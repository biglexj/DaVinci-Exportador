"""Tokens visuales de la interfaz.

Un solo tema, semMaterial, compacto y legible sobre fondo oscuro. Los colores
semánticos se usan para distinguir estados (correcto, aviso, error) sin
depender del color de un componente concreto.
"""

import flet as ft

TEMA = ft.Theme(
    color_scheme_seed=ft.Colors.INDIGO_300,
    use_material3=True,
    visual_density=ft.VisualDensity.COMFORTABLE,
)

COLOR_OK = ft.Colors.GREEN_300
COLOR_AVISO = ft.Colors.AMBER_300
COLOR_ERROR = ft.Colors.RED_300
COLOR_TENUE = ft.Colors.ON_SURFACE_VARIANT
COLOR_SUPERFICIE = ft.Colors.SURFACE_CONTAINER_LOW
COLOR_SUPERFICIE_ALTA = ft.Colors.SURFACE_CONTAINER_HIGH
COLOR_BORDE = ft.Colors.OUTLINE_VARIANT

RADIO = 10
ESPACIO = 16
