"""Gestor y empaquetador de plantillas Fusion en archivos .drfx.

Inspecciona la estructura de carpetas de plantillas (Edit/Titles, Edit/Effects, etc.),
presenta el catálogo detallado de plantillas .setting y recursos, permite configurar
metadatos de autoría y empaqueta en paquetes .drfx verificados, manteniendo un
historial de paquetes creados.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import queue
import threading

import flet as ft

from app.tema import COLOR_AVISO, COLOR_BORDE, COLOR_ERROR, COLOR_OK, COLOR_TENUE, RADIO
from davinci_exportador.controller import (
    ResultadoPaquete,
    abrir_en_el_sistema,
    comprobar_plantillas,
    empaquetar_plantillas,
    explicar_error,
    obtener_historial_paquetes,
)
from shared import components as controles
from shared.components import refrescar

MODO_TALLER = "taller"
MODO_HISTORIAL = "historial"

ICONOS_CATEGORIA = {
    "Titles": ft.Icons.TITLE,
    "Effects": ft.Icons.AUTO_AWESOME,
    "Generators": ft.Icons.WIDGETS,
    "Transitions": ft.Icons.SHUFFLE,
}


def _formatear_tamano(bytes_totales: int) -> str:
    """Devuelve un tamaño en bytes legible para humanos."""
    if bytes_totales < 1024:
        return f"{bytes_totales} B"
    if bytes_totales < 1024 * 1024:
        return f"{bytes_totales / 1024:.1f} KB"
    return f"{bytes_totales / (1024 * 1024):.1f} MB"


class VistaEmpaquetar:
    """Vista principal: Taller de empaquetado e historial de paquetes .drfx."""

    def __init__(self, page: ft.Page, selector: ft.FilePicker):
        self.page = page
        self.selector = selector
        self.carpeta: Path | None = None
        self.informe: dict | None = None
        self.ruta_salida: Path | None = None
        self.paquete_creado = False
        self.cola: queue.Queue = queue.Queue()
        self.modo_activo = MODO_TALLER
        self._construir()

    # ----------------------------------------------------------------- #
    # Construcción de la vista
    # ----------------------------------------------------------------- #

    def _construir(self) -> None:
        # Selector de vista interna: Taller vs Historial
        self.selector_pestaña = ft.SegmentedButton(
            segments=[
                ft.Segment(value=MODO_TALLER, label="Empaquetar colección", icon=ft.Icons.INVENTORY_2),
                ft.Segment(value=MODO_HISTORIAL, label="Historial de paquetes", icon=ft.Icons.HISTORY),
            ],
            selected=[MODO_TALLER],
            on_change=self._cambiar_subvista,
        )

        # Paso 1: Carpeta origen
        self.campo_carpeta = ft.TextField(
            label="Carpeta de plantillas",
            read_only=True,
            expand=True,
            hint_text="Ninguna seleccionada",
        )
        self.mensaje_carpeta = ft.Container(visible=False)
        self.ayuda_inicial = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Cómo preparar la carpeta", size=13, weight=ft.FontWeight.W_600, color=COLOR_TENUE),
                    ft.Text(
                        "Selecciona la carpeta raíz que contiene la subcarpeta 'Edit/' con una o más de "
                        "las categorías oficiales de DaVinci Resolve: Edit/Titles, Edit/Effects, "
                        "Edit/Generators o Edit/Transitions.",
                        size=13,
                        color=COLOR_TENUE,
                    ),
                    ft.Text(
                        "Los recursos auxiliares (.png, .jpg, .lut, etc.) ubicados junto a las plantillas "
                        "se incluirán automáticamente dentro del paquete .drfx.",
                        size=12,
                        color=COLOR_TENUE,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=RADIO,
        )

        # Paso 2: Catálogo de plantillas
        self.panel_catalogo = ft.Container(visible=False)

        # Paso 3: Metadatos y Destino
        self.campo_autor = ft.TextField(
            label="Autor / Creador",
            value="Biglex J",
            expand=True,
            hint_text="Nombre o firma del autor",
        )
        self.campo_version = ft.TextField(
            label="Versión",
            value="1.0.0",
            width=140,
            hint_text="1.0.0",
        )
        self.campo_salida = ft.TextField(
            label="Paquete .drfx de destino",
            read_only=True,
            expand=True,
            hint_text="Ninguno seleccionado",
        )
        self.texto_salida = ft.Text("", size=12, color=COLOR_TENUE, selectable=True)
        self.seccion_destino = ft.Container(
            content=ft.Column(
                controls=[
                    controles.paso(
                        3,
                        "Metadatos y destino del paquete",
                        "Indica la autoría y la ubicación del archivo .drfx final (no se sobrescribe).",
                    ),
                    ft.Row(controls=[self.campo_autor, self.campo_version], spacing=12),
                    ft.Row(
                        controls=[
                            ft.Button(
                                content="Elegir destino…",
                                icon=ft.Icons.SAVE,
                                on_click=self.elegir_salida,
                            ),
                            self.campo_salida,
                        ],
                        spacing=10,
                    ),
                    self.texto_salida,
                ],
                spacing=12,
            ),
            visible=False,
        )

        # Resultado y progreso
        self.panel_resultado = ft.Container(visible=False, key="resultado")
        self.barra_progreso = ft.ProgressBar(value=0, visible=False, width=220)
        self.texto_progreso = ft.Text("", size=12, color=COLOR_TENUE, visible=False)
        self.boton_crear = ft.Button(
            content="Crear paquete .drfx",
            icon=ft.Icons.INVENTORY,
            on_click=self.crear_paquete,
            disabled=True,
            height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        )
        self.estado = ft.Text("Elige una carpeta de plantillas para empezar.", size=13, color=COLOR_TENUE, expand=True)
        self.fila_resultado = ft.Row(visible=False, spacing=10)

        # Contenedor del Taller
        self.columna_taller = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            controles.paso(
                                1,
                                "Elegir carpeta de plantillas",
                                "Debe contener Edit/Titles, Edit/Effects, Edit/Generators o Edit/Transitions.",
                            ),
                            ft.Row(
                                controls=[
                                    ft.Button(
                                        content="Elegir carpeta…",
                                        icon=ft.Icons.FOLDER_OPEN,
                                        on_click=self.elegir_carpeta,
                                    ),
                                    self.campo_carpeta,
                                ],
                                spacing=10,
                            ),
                            self.mensaje_carpeta,
                            self.ayuda_inicial,
                        ],
                        spacing=10,
                    )
                ),
                self.panel_catalogo,
                self.seccion_destino,
                self.panel_resultado,
            ],
            spacing=18,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        # Contenedor del Historial
        self.columna_historial = ft.Column(
            controls=[],
            spacing=14,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            visible=False,
        )

        # Barra inferior de acciones
        self.barra_inferior = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(controls=[self.estado, self.texto_progreso], spacing=2, expand=True),
                            self.barra_progreso,
                            self.boton_crear,
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.fila_resultado,
                ],
                spacing=8,
            ),
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

        self.area_contenido = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self.selector_pestaña,
                            ft.Container(expand=True),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    self.columna_taller,
                    self.columna_historial,
                ],
                spacing=14,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            expand=True,
        )

        self.raiz = ft.Column(
            controls=[
                self.area_contenido,
                self.barra_inferior,
            ],
            spacing=0,
            expand=True,
        )

    # ----------------------------------------------------------------- #
    # Navegación entre Taller e Historial
    # ----------------------------------------------------------------- #

    def _cambiar_subvista(self, evento) -> None:
        elegido = evento.control.selected[0] if evento.control.selected else MODO_TALLER
        self.modo_activo = elegido
        self.columna_taller.visible = elegido == MODO_TALLER
        self.columna_historial.visible = elegido == MODO_HISTORIAL
        self.barra_inferior.visible = elegido == MODO_TALLER

        if elegido == MODO_HISTORIAL:
            self._renderizar_historial()

        refrescar(self.columna_taller)
        refrescar(self.columna_historial)
        refrescar(self.barra_inferior)

    def _renderizar_historial(self) -> None:
        """Carga y muestra el historial de paquetes creados."""
        historial = obtener_historial_paquetes()
        self.columna_historial.controls.clear()

        encabezado = ft.Row(
            controls=[
                ft.Icon(ft.Icons.HISTORY, size=20, color=ft.Colors.PRIMARY),
                ft.Text("Historial de paquetes creados", size=16, weight=ft.FontWeight.W_600),
                ft.Container(expand=True),
                ft.Button(
                    content="Actualizar",
                    icon=ft.Icons.REFRESH,
                    on_click=lambda e: self._renderizar_historial(),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.columna_historial.controls.append(encabezado)

        if not historial:
            vacio = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.INBOX, size=40, color=COLOR_TENUE),
                        ft.Text(
                            "Aún no se han generado paquetes .drfx desde esta app.",
                            size=14,
                            color=COLOR_TENUE,
                        ),
                        ft.Text(
                            "Los paquetes que crees en el taller quedarán registrados aquí con su fecha, "
                            "conteo de plantillas y ruta de acceso.",
                            size=12,
                            color=COLOR_TENUE,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=ft.Padding.symmetric(vertical=40, horizontal=20),
                alignment=ft.Alignment.CENTER,
            )
            self.columna_historial.controls.append(vacio)
            refrescar(self.columna_historial)
            return

        for item in historial:
            paquete_path = Path(item.get("paquete", ""))
            nombre = item.get("nombre", paquete_path.name or "paquete.drfx")
            fecha = item.get("fecha", "Fecha desconocida")
            titulos = item.get("titulos", 0)
            archivos = item.get("archivos", 0)
            autor = item.get("autor", "Biglex J")
            version = item.get("version", "1.0.0")
            sha256 = item.get("sha256", "")[:12]

            tarjeta = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ARCHIVE, size=28, color=ft.Colors.PRIMARY),
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(nombre, size=14, weight=ft.FontWeight.W_600),
                                        ft.Container(
                                            content=ft.Text(f"v{version}", size=11, color=ft.Colors.PRIMARY),
                                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                        ft.Text(f"por {autor}", size=12, color=COLOR_TENUE),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(
                                    f"{titulos} plantillas (.setting) · {archivos} archivos · "
                                    f"Creado el {fecha} · SHA256 {sha256}…",
                                    size=12,
                                    color=COLOR_TENUE,
                                ),
                                controles.ruta_texto(str(paquete_path)),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                        ft.Button(
                            content="Abrir carpeta",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda e, p=paquete_path: abrir_en_el_sistema(p.parent),
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                border_radius=RADIO,
                border=ft.Border.all(1, COLOR_BORDE),
            )
            self.columna_historial.controls.append(tarjeta)

        refrescar(self.columna_historial)

    # ----------------------------------------------------------------- #
    # Paso 1: Carpeta
    # ----------------------------------------------------------------- #

    async def elegir_carpeta(self, evento) -> None:
        carpeta = await self.selector.get_directory_path(
            dialog_title="Elige la carpeta de plantillas que contiene Edit/"
        )
        if not carpeta:
            return
        self.cargar_carpeta(Path(carpeta))

    def cargar_carpeta(self, carpeta: Path) -> None:
        self.carpeta = carpeta
        self.campo_carpeta.value = str(carpeta)
        self.ayuda_inicial.visible = False
        refrescar(self.ayuda_inicial)
        informe, error = comprobar_plantillas(carpeta)
        if error:
            self.informe = None
            self.mensaje_carpeta.content = controles.mensaje(error, "error")
            self.mensaje_carpeta.visible = True
            self.panel_catalogo.visible = False
            self.seccion_destino.visible = False
            self.boton_crear.disabled = True
            self.estado.value = "La carpeta no cumple la estructura necesaria de DaVinci Resolve."
        else:
            self.informe = informe
            self.mensaje_carpeta.visible = False
            self.mensaje_carpeta.content = None
            self._pintar_catalogo(informe)
            self.seccion_destino.visible = True
            self.estado.value = "Indica los metadatos y el destino del paquete .drfx."
            # Autocompletar nombre sugerido si no hay salida fijada
            if self.ruta_salida is None:
                nombre_sugerido = carpeta.name + ".drfx"
                self.ruta_salida = carpeta.parent / nombre_sugerido
                self.campo_salida.value = str(self.ruta_salida)
                self._comprobar_salida()

        refrescar(self.campo_carpeta)
        refrescar(self.mensaje_carpeta)
        refrescar(self.panel_catalogo)
        refrescar(self.seccion_destino)
        refrescar(self.boton_crear)
        refrescar(self.estado)

    # ----------------------------------------------------------------- #
    # Paso 2: Catálogo de plantillas inspeccionadas
    # ----------------------------------------------------------------- #

    def _pintar_catalogo(self, informe: dict) -> None:
        """Presenta el resumen enriquecido y el listado de plantillas detectadas."""
        settings_count = informe.get("settings", 0)
        resources_count = informe.get("resources", 0)
        total_files = informe.get("files", 0)
        categories_summary = informe.get("categories_summary", {})
        templates = informe.get("templates", [])

        # Chips de categorías
        chips = []
        for cat, count in categories_summary.items():
            if count > 0:
                icono = ICONOS_CATEGORIA.get(cat, ft.Icons.CATEGORY)
                chips.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(icono, size=15, color=ft.Colors.PRIMARY),
                                ft.Text(f"{cat}: {count}", size=12, weight=ft.FontWeight.W_500),
                            ],
                            spacing=6,
                        ),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=8,
                        border=ft.Border.all(1, COLOR_BORDE),
                    )
                )

        if resources_count > 0:
            chips.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE, size=15, color=COLOR_TENUE),
                            ft.Text(f"Recursos: {resources_count}", size=12, color=COLOR_TENUE),
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=8,
                    border=ft.Border.all(1, COLOR_BORDE),
                )
            )

        # Construir lista de items de plantillas para el ExpansionTile
        filas_plantillas = []
        for t in templates:
            cat = t.get("category", "")
            icono_t = ICONOS_CATEGORIA.get(cat, ft.Icons.TITLE)
            subf = f"  [{t['subfolder']}]" if t.get("subfolder") else ""
            tam = _formatear_tamano(t.get("size_bytes", 0))

            filas_plantillas.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icono_t, size=16, color=ft.Colors.PRIMARY),
                            ft.Text(t.get("name", ""), size=13, weight=ft.FontWeight.W_500),
                            ft.Text(subf, size=12, color=COLOR_TENUE),
                            ft.Container(expand=True),
                            ft.Text(tam, size=11, color=COLOR_TENUE),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                )
            )

        acordeon_catalogo = ft.ExpansionTile(
            title=ft.Text(f"Catálogo detectado ({settings_count} plantillas)", size=13, weight=ft.FontWeight.W_600),
            subtitle=ft.Text("Haz clic para desplegar los títulos individuales", size=11, color=COLOR_TENUE),
            leading=ft.Icon(ft.Icons.LIST_ALT, color=ft.Colors.PRIMARY),
            controls=filas_plantillas,
        )

        self.panel_catalogo.content = ft.Container(
            content=ft.Column(
                controls=[
                    controles.paso(
                        2,
                        "Catálogo e inspección de plantillas",
                        f"Se detectaron {settings_count} plantillas listas y {resources_count} recursos auxiliares.",
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLOR_OK, size=18),
                                        ft.Text(
                                            "Estructura correcta de DaVinci Resolve",
                                            size=14,
                                            weight=ft.FontWeight.W_600,
                                            color=COLOR_OK,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    f"Total: {total_files} archivos listos para empaquetar.",
                                    size=12,
                                    color=COLOR_TENUE,
                                ),
                                ft.Row(controls=chips, wrap=True, spacing=8),
                                ft.Divider(height=1, color=COLOR_BORDE),
                                acordeon_catalogo,
                            ],
                            spacing=10,
                        ),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                        border_radius=RADIO,
                        border=ft.Border(left=ft.BorderSide(3, COLOR_OK)),
                    ),
                ],
                spacing=12,
            ),
        )
        self.panel_catalogo.visible = True

    # ----------------------------------------------------------------- #
    # Paso 3: Destino y Metadatos
    # ----------------------------------------------------------------- #

    async def elegir_salida(self, evento) -> None:
        nombre = self.carpeta.name + ".drfx" if self.carpeta else "plantillas.drfx"
        ruta = await self.selector.save_file(
            dialog_title="Guardar el paquete .drfx",
            file_name=nombre,
            allowed_extensions=["drfx"],
        )
        if not ruta:
            return
        self.ruta_salida = Path(ruta)
        self.campo_salida.value = str(self.ruta_salida)
        self._comprobar_salida()

    def _comprobar_salida(self) -> None:
        problemas = []
        aviso = False
        if self.ruta_salida is None:
            problemas.append("Elige dónde guardar el paquete .drfx.")
        elif self.ruta_salida.exists():
            if self.paquete_creado:
                problemas.append(
                    f"El paquete «{self.ruta_salida.name}» ya está creado. "
                    "Para rehacerlo, elige otro nombre."
                )
                aviso = True
            else:
                problemas.append(
                    f"Ya existe «{self.ruta_salida.name}». Elige otro nombre: no se sobrescribe nada."
                )
        self.texto_salida.value = problemas[0] if problemas else ""
        self.texto_salida.color = COLOR_AVISO if aviso else ft.Colors.RED_300
        refrescar(self.texto_salida)
        self.boton_crear.disabled = bool(problemas) or self.carpeta is None
        refrescar(self.boton_crear)
        refrescar(self.campo_salida)

    # ----------------------------------------------------------------- #
    # Paso 4: Ejecución
    # ----------------------------------------------------------------- #

    async def crear_paquete(self, evento) -> None:
        if self.boton_crear.disabled:
            return
        if self.carpeta is None or self.ruta_salida is None:
            return
        carpeta, salida = self.carpeta, self.ruta_salida
        metadata = {
            "author": self.campo_autor.value.strip() or "Biglex J",
            "version": self.campo_version.value.strip() or "1.0.0",
        }

        self.boton_crear.disabled = True
        self.barra_progreso.visible = True
        self.barra_progreso.value = 0
        self.texto_progreso.visible = True
        self.texto_progreso.value = "Empaquetando…"
        self.estado.value = "Creando el paquete .drfx…"
        self.fila_resultado.visible = False
        refrescar(self.fila_resultado)
        refrescar(self.barra_progreso)
        refrescar(self.texto_progreso)
        refrescar(self.estado)
        refrescar(self.boton_crear)

        self.cola = queue.Queue()

        def progreso(hechos: int, total: int, mensaje: str) -> None:
            self.cola.put(("avance", hechos, total, mensaje))

        def trabajo() -> None:
            try:
                resultado = empaquetar_plantillas(carpeta, salida, progreso=progreso, metadata=metadata)
                self.cola.put(("fin", resultado, None))
            except Exception as exc:  # noqa: BLE001
                self.cola.put(("fin", None, exc))

        threading.Thread(target=trabajo, daemon=True).start()
        await self._esperar()
        self._comprobar_salida()

    async def _esperar(self) -> None:
        while True:
            try:
                item = self.cola.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if item[0] == "avance":
                _, hechos, total, mensaje = item
                self.barra_progreso.value = (hechos / total) if total else None
                self.texto_progreso.value = f"{hechos} de {total} · {mensaje}"
                refrescar(self.barra_progreso)
                refrescar(self.texto_progreso)
                continue
            _, resultado, error = item
            self.barra_progreso.visible = False
            self.texto_progreso.visible = False
            refrescar(self.barra_progreso)
            refrescar(self.texto_progreso)
            if error is not None:
                mensaje, pista = explicar_error(error)
                await self.mostrar_resultado_error(mensaje, pista)
                self.estado.value = "El paquete no se creó."
                refrescar(self.estado)
                return
            await self._finalizar(resultado)
            return

    async def _finalizar(self, resultado: ResultadoPaquete) -> None:
        self.estado.value = "Paquete creado con éxito."
        self.paquete_creado = True
        refrescar(self.estado)

        async def consultar_informe(evento) -> None:
            self._mostrar_informe(resultado)

        self.fila_resultado.controls = [
            ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLOR_OK, size=18),
            ft.Text(f"Paquete listo: {resultado.paquete.name}", size=13, color=COLOR_OK, expand=True),
            ft.Button(
                content="Abrir carpeta",
                icon=ft.Icons.FOLDER_OPEN,
                on_click=lambda e: abrir_en_el_sistema(resultado.paquete.parent),
            ),
            ft.Button(
                content="Consultar informe",
                icon=ft.Icons.DESCRIPTION,
                on_click=consultar_informe,
            ),
        ]
        self.fila_resultado.visible = True
        refrescar(self.fila_resultado)

        autor = resultado.metadata.get("author", "Biglex J")
        version = resultado.metadata.get("version", "1.0.0")

        piezas = [
            ft.Text("Paquete .drfx creado con éxito", size=14, weight=ft.FontWeight.W_600, color=COLOR_OK),
            controles.ruta_texto(str(resultado.paquete)),
            ft.Text(
                f"{resultado.titulos} títulos · {resultado.archivos} archivos · "
                f"v{version} por {autor} · SHA256 {resultado.sha256[:16]}…",
                size=12,
                color=COLOR_TENUE,
            ),
            ft.Text(
                "La integridad del paquete está comprobada. Listo para instalarse en DaVinci Resolve o distribuirse.",
                size=12,
                color=COLOR_TENUE,
            ),
            ft.Row(
                controls=[
                    ft.Button(
                        content="Abrir carpeta",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=lambda e: abrir_en_el_sistema(resultado.paquete.parent),
                    ),
                    ft.Button(
                        content="Consultar informe",
                        icon=ft.Icons.DESCRIPTION,
                        on_click=consultar_informe,
                    ),
                ],
                spacing=10,
            ),
        ]
        self.panel_resultado.content = ft.Container(
            content=ft.Column(controls=piezas, spacing=8),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=RADIO,
            border=ft.Border(left=ft.BorderSide(3, COLOR_OK)),
        )
        self.panel_resultado.visible = True
        refrescar(self.panel_resultado)

    async def mostrar_resultado_error(self, texto: str, pista: str = "") -> None:
        self.panel_resultado.content = controles.mensaje(texto, pista, "error")
        self.panel_resultado.visible = True
        refrescar(self.panel_resultado)
        self.fila_resultado.controls = [
            ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=18),
            ft.Text(f"{texto} {pista}".strip(), size=13, color=COLOR_ERROR, expand=True),
        ]
        self.fila_resultado.visible = True
        refrescar(self.fila_resultado)

    def _mostrar_informe(self, resultado: ResultadoPaquete) -> None:
        autor = resultado.metadata.get("author", "Biglex J")
        version = resultado.metadata.get("version", "1.0.0")

        lineas = [
            f"Paquete: {resultado.paquete.name}",
            f"Ruta completa: {resultado.paquete}",
            f"Autor: {autor}",
            f"Versión: {version}",
            f"Plantillas (.setting): {resultado.titulos}",
            f"Archivos totales incluidos: {resultado.archivos}",
            f"SHA256: {resultado.sha256}",
            "",
            "El archivo .drfx es un contenedor ZIP estándar de Fusion.",
            "La integridad de compresión fue verificada correctamente.",
            "No se ha instalado en Resolve ni se ha probado su renderizado interno.",
        ]
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Informe del paquete .drfx"),
            content=ft.Container(
                content=ft.ListView(
                    controls=[ft.Text("\n".join(lineas), size=12, selectable=True, font_family="Consolas")],
                    expand=True,
                ),
                height=280,
                width=540,
            ),
            actions=[ft.Button(content="Cerrar", on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialogo)
