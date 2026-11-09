"""Operación 1: exportar títulos a una carpeta de plantillas.

Recorrido: elegir origen → seleccionar contenido → revisar destino → exportar.
La vista solo muestra datos y recoge decisiones; toda la lógica de conversión
vive en el paquete ``davinci_exportador`` (``src/davinci_exportador``), que no
depende de Flet.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from pathlib import Path

import flet as ft

from davinci_exportador.controller import (
    ResultadoExportacion,
    abrir_en_el_sistema,
    explicar_error,
    exportar_titulos,
)
from davinci_exportador.inventario import ComposicionInfo, Inventario, inventariar
from davinci_exportador.lectura import EXTENSIONES_ENTRADA
from davinci_exportador.reglas import (
    OpcionesNombres,
    ReglaCarpeta,
    comprobar_destino,
    construir_config,
    previsualizar,
    rutas_en_conflicto,
)
from shared import components as controles
from shared.components import refrescar
from app.tema import COLOR_AVISO, COLOR_ERROR, COLOR_OK, COLOR_TENUE, RADIO


class VistaExportarTitulos:
    """Vista de exportación de títulos."""

    def __init__(self, page: ft.Page, selector: ft.FilePicker):
        self.page = page
        self.selector = selector
        self.inventario = Inventario()
        self.seleccion: set[tuple[str, str]] = set()
        self.reglas: dict[str, ReglaCarpeta] = {}
        self.carpeta_destino: Path | None = None
        self.nombre_carpeta = "titulos-exportados"
        self.crear_paquete = False
        self.ruta_paquete_manual: Path | None = None
        self.cola: queue.Queue = queue.Queue()
        self.casillas: dict[tuple[str, str], ft.Checkbox] = {}
        self.contadores: dict[str, ft.Text] = {}
        self.campos_regla: dict[str, dict[str, ft.TextField]] = {}
        self.opciones = OpcionesNombres(creador="Biglex J")
        self._construir()

    # ----------------------------------------------------------------- #
    # Construcción de la vista
    # ----------------------------------------------------------------- #

    def _construir(self) -> None:
        self.campo_origen = ft.TextField(
            label="Archivo de origen", read_only=True, expand=True,
            hint_text="Ninguno seleccionado",
        )
        self._construir_ayuda()
        self.mensaje_origen = ft.Container(visible=False)
        self.contador_general = ft.Text("", size=12, color=COLOR_TENUE)

        self.seccion_contenido = ft.Container(visible=False)
        self.seccion_destino = ft.Container(visible=False)
        self.panel_resultado = ft.Container(visible=False, key="resultado")

        self.barra_progreso = ft.ProgressBar(value=0, visible=False, width=220)
        self.texto_progreso = ft.Text("", size=12, color=COLOR_TENUE, visible=False)
        self.boton_exportar = ft.Button(
            content="Exportar títulos",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.exportar,
            disabled=True,
            height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        )
        self.estado = ft.Text("Elige un archivo de origen para empezar.", size=13, color=COLOR_TENUE, expand=True)
        # El resultado se muestra en la barra fija: siempre está a la vista.
        self.fila_resultado = ft.Row(visible=False, spacing=10)

        self.contenido = ft.Column(
            controls=[
                self._bloque_origen(),
                self.seccion_contenido,
                self.seccion_destino,
                self.panel_resultado,
            ],
            spacing=18,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        # El contenido lleva margen a los lados: nada toca el borde de la ventana.
        self.area_contenido = ft.Container(
            content=self.contenido,
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            expand=True,
        )
        self.raiz = ft.Column(
            controls=[
                self.area_contenido,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Column(controls=[self.estado, self.texto_progreso], spacing=2, expand=True),
                                    self.barra_progreso,
                                    self.boton_exportar,
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
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _bloque_origen(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    controles.paso(
                        1, "Elegir origen",
                        "Una bandeja o proyecto exportado desde Resolve (.drb, .drp) o un archivo .comp o .setting.",
                    ),
                    ft.Row(
                        controls=[
                            ft.Button(
                                content="Elegir archivo…", icon=ft.Icons.FOLDER_OPEN,
                                on_click=self.elegir_origen,
                            ),
                            self.campo_origen,
                        ],
                        spacing=10,
                    ),
                    self.mensaje_origen,
                    self.ayuda_inicial,
                ],
                spacing=10,
            )
        )

    def _construir_ayuda(self) -> None:
        """Explica qué hace la app mientras no hay origen elegido."""
        self.ayuda_inicial = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Qué hace esto", size=13, weight=ft.FontWeight.W_600, color=COLOR_TENUE),
                    ft.Text(
                        "Convierte las composiciones Fusion de una bandeja exportada en títulos .setting "
                        "y los reúne en un paquete .drfx que se puede instalar en Resolve.",
                        size=13, color=COLOR_TENUE),
                    ft.Text(
                        "Los archivos se leen de una copia exportada: la app no abre tu proyecto, no modifica "
                        "composiciones y no instala nada en Resolve. La conversión no comprueba el render "
                        "ni los botones personalizados del Inspector.",
                        size=13, color=COLOR_TENUE),
                    ft.Text(
                        "Para ver solo el empaquetado de una carpeta de plantillas, cambia al otro modo "
                        "arriba a la derecha.",
                        size=13, color=COLOR_TENUE),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=RADIO,
        )

    # ----------------------------------------------------------------- #
    # Paso 1: origen
    # ----------------------------------------------------------------- #

    async def elegir_origen(self, evento) -> None:
        archivos = await self.selector.pick_files(
            dialog_title="Elegir la bandeja o el archivo de origen",
            allowed_extensions=list(EXTENSIONES_ENTRADA),
        )
        if not archivos:
            return
        self.cargar_origen(Path(archivos[0].path))

    def cargar_origen(self, origen: Path) -> None:
        self.inventario = inventariar(origen)
        self.seleccion = set()
        self.campo_origen.value = str(origen)
        self.ayuda_inicial.visible = False
        refrescar(self.ayuda_inicial)
        if self.inventario.error:
            self.mostrar_mensaje_origen(self.inventario.error, "error")
            self.seccion_contenido.visible = False
            self.seccion_destino.visible = False
            self.estado.value = "No se pudo leer el origen."
            self.boton_exportar.disabled = True
            refrescar(self.campo_origen)
            refrescar(self.seccion_contenido)
            refrescar(self.seccion_destino)
            refrescar(self.estado)
            return
        self.mostrar_mensaje_origen("", "ok")
        self._pintar_contenido()
        self._pintar_destino()
        refrescar(self.campo_origen)
        refrescar(self.seccion_contenido)
        refrescar(self.seccion_destino)

    def mostrar_mensaje_origen(self, texto: str, tono: str) -> None:
        if not texto:
            self.mensaje_origen.visible = False
            self.mensaje_origen.content = None
        else:
            self.mensaje_origen.content = controles.mensaje(texto, tono=tono)
            self.mensaje_origen.visible = True
        refrescar(self.mensaje_origen)

    # ----------------------------------------------------------------- #
    # Paso 2: selección de contenido
    # ----------------------------------------------------------------- #

    def _pintar_contenido(self) -> None:
        self.casillas = {}
        self.contadores = {}
        inventario = self.inventario
        bloques = []
        if inventario.problemas:
            bloques.append(controles.mensaje(
                "Algunas entradas del archivo no se pudieron leer:", tono="aviso"))
            bloques.append(ft.Column(
                controls=[ft.Text(problema, size=12, color=COLOR_TENUE) for problema in inventario.problemas],
                spacing=2,
            ))
        if not inventario.composiciones:
            bloques.append(controles.mensaje(
                "El archivo no contiene composiciones exportables.",
                "Exporta desde Resolve la bandeja o el proyecto que contiene los títulos.",
                "error",
            ))
            self.seccion_contenido.content = ft.Column(controls=bloques, spacing=10)
            self.seccion_contenido.visible = True
            self.boton_exportar.disabled = True
            self.estado.value = "El origen no contiene composiciones utilizables."
            refrescar(self.estado)
            return

        for carpeta in inventario.carpetas:
            bloques.append(self._bloque_carpeta(carpeta))
        incompatibles = [c for c in inventario.composiciones if not c.compatible]
        if incompatibles:
            bloques.append(ft.Text(
                f"{len(incompatibles)} composición(es) no se pueden exportar: necesitan un único TextPlus "
                "y un MediaOut en el nivel raíz. Pasa el ratón por el aviso para ver el motivo.",
                size=12, color=COLOR_TENUE,
            ))

        # La selección es la única región que crece: se desplaza por dentro
        # para que el resto del recorrido siga a la vista.
        lista_seleccion = ft.ListView(controls=bloques, height=220, spacing=8, padding=0)
        self.seccion_contenido.content = ft.Column(
            controls=[
                controles.paso(2, "Seleccionar contenido",
                               "Marca las composiciones que quieres exportar."),
                ft.Row(
                    controls=[
                        ft.Button(content="Marcar compatibles", icon=ft.Icons.CHECK_CIRCLE,
                                  on_click=self.marcar_compatibles),
                        ft.Button(content="Desmarcar todo", icon=ft.Icons.CLEAR,
                                  on_click=self.desmarcar_todo),
                        self.contador_general,
                    ],
                    spacing=10,
                ),
                lista_seleccion,
            ],
            spacing=10,
        )
        self.seccion_contenido.visible = True
        self.actualizar_contadores()
        self.boton_exportar.disabled = True
        self.estado.value = "Selecciona las composiciones que quieres exportar."

    def _bloque_carpeta(self, carpeta: str) -> ft.Container:
        composiciones = [c for c in self.inventario.composiciones if c.carpeta == carpeta]
        casilla_carpeta = ft.Checkbox(value=False, on_change=self.al_cambiar_carpeta, data=carpeta)
        contador = ft.Text("", size=12, color=COLOR_TENUE, expand=True)
        self.contadores[carpeta] = contador
        filas = [self._fila_composicion(info) for info in composiciones]
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            casilla_carpeta,
                            ft.Text(carpeta, size=14, weight=ft.FontWeight.W_600),
                            contador,
                        ],
                        spacing=8,
                    ),
                    *filas,
                ],
                spacing=2,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=RADIO,
        )

    def _fila_composicion(self, info: ComposicionInfo) -> ft.Row:
        if info.compatible:
            casilla = ft.Checkbox(value=False, on_change=self.al_cambiar_composicion, data=info.clave)
            self.casillas[info.clave] = casilla
            pendientes = []
            if info.medios:
                pendientes.append(f"medios externos: {', '.join(info.medios)}")
            if info.fuentes:
                pendientes.append(f"fuentes: {', '.join(info.fuentes)}")
            estado = ft.Text("Compatible", size=12, color=COLOR_OK)
            if pendientes:
                estado = ft.Text("Compatible · " + " · ".join(pendientes), size=12, color=COLOR_AVISO)
            return ft.Row(
                controls=[casilla, ft.Text(info.nombre, size=13, expand=True), estado],
                spacing=8,
            )
        etiqueta = ft.Text("No compatible", size=12, color=COLOR_ERROR,
                           tooltip=ft.Tooltip(message=info.motivo))
        return ft.Row(
            controls=[
                ft.Checkbox(value=False, disabled=True),
                ft.Text(info.nombre, size=13, color=COLOR_TENUE, expand=True),
                etiqueta,
            ],
            spacing=8,
        )

    def al_cambiar_composicion(self, evento) -> None:
        clave = evento.control.data
        if evento.control.value:
            self.seleccion.add(clave)
        else:
            self.seleccion.discard(clave)
        self.actualizar_contadores()
        self.actualizar_previsualizacion()

    def al_cambiar_carpeta(self, evento) -> None:
        carpeta = evento.control.data
        for info in self.inventario.composiciones:
            if info.carpeta != carpeta:
                continue
            casilla = self.casillas.get(info.clave)
            if casilla is None:
                continue
            casilla.value = bool(evento.control.value)
            if evento.control.value:
                self.seleccion.add(info.clave)
            else:
                self.seleccion.discard(info.clave)
        self.actualizar_contadores()
        self.actualizar_previsualizacion()

    def marcar_compatibles(self, evento) -> None:
        for clave, casilla in self.casillas.items():
            casilla.value = True
            self.seleccion.add(clave)
        self.actualizar_contadores()
        self.actualizar_previsualizacion()

    def desmarcar_todo(self, evento) -> None:
        for clave, casilla in self.casillas.items():
            casilla.value = False
            self.seleccion.discard(clave)
        self.actualizar_contadores()
        self.actualizar_previsualizacion()

    def actualizar_contadores(self) -> None:
        for carpeta, contador in self.contadores.items():
            elegibles = [c for c in self.inventario.composiciones
                         if c.carpeta == carpeta and c.clave in self.casillas]
            marcadas = sum(1 for c in elegibles if c.clave in self.seleccion)
            contador.value = f"{marcadas} de {len(elegibles)} seleccionadas"
            refrescar(contador)
        self.contador_general.value = f"{len(self.seleccion)} seleccionadas"
        refrescar(self.contador_general)

    # ----------------------------------------------------------------- #
    # Paso 3: atribución, nombres y destino
    # ----------------------------------------------------------------- #

    def _pintar_destino(self) -> None:
        self.campo_creador = ft.TextField(label="Creador", value="Biglex J", col={"xs": 12, "md": 6},
                                          on_change=self.al_cambiar_nombres)
        self.campo_coleccion = ft.TextField(label="Colección", value="", col={"xs": 12, "md": 6},
                                            on_change=self.al_cambiar_nombres)
        self.campo_prefijo = ft.TextField(label="Nombre base (prefijo)", value="", col={"xs": 12, "md": 6},
                                          on_change=self.al_cambiar_nombres)
        self.campo_credito = ft.TextField(label="Crédito (opcional)", value="", col={"xs": 12, "md": 6},
                                          on_change=self.al_cambiar_nombres)
        self.campo_destino = ft.TextField(label="Carpeta de destino", read_only=True, expand=True,
                                          hint_text="Ninguna seleccionada")
        self.campo_nombre_carpeta = ft.TextField(label="Nombre de la carpeta nueva", value=self.nombre_carpeta,
                                                 on_change=self.al_cambiar_nombres)
        self.campo_paquete = ft.TextField(label="Paquete .drfx", read_only=True, expand=True,
                                          hint_text="Se propondrá al terminar", visible=False)
        self.texto_destino = ft.Text("", size=12, color=COLOR_TENUE, selectable=True)
        self.lista_previa = ft.ListView(height=170, spacing=0, padding=0)
        self.mensaje_previa = ft.Container(visible=False)
        self.casilla_paquete = ft.Checkbox(label="Crear un paquete .drfx al terminar", value=False,
                                           on_change=self.al_cambiar_paquete)
        self.boton_elegir_paquete = ft.Button(content="Elegir archivo del paquete…", icon=ft.Icons.SAVE,
                                              on_click=self.elegir_ruta_paquete, visible=False)
        self.campo_avanzado_quitar = ft.TextField(label="Quitar prefijo del nombre (opcional)", value="",
                                                  on_change=self.al_cambiar_nombres)
        self.campo_avanzado_guiones = ft.Checkbox(label="Cambiar guiones por espacios", value=False,
                                                  on_change=self.al_cambiar_nombres)
        self.campo_avanzado_mayusculas = ft.Checkbox(label="Empezar el nombre en mayúscula", value=False,
                                                     on_change=self.al_cambiar_nombres)
        self.campo_avanzado_medios = ft.Checkbox(
            label="Permitir títulos que usan medios externos (no se incrustan)", value=False,
            on_change=self.al_cambiar_nombres)

        self.seccion_destino.content = ft.Column(
            controls=[
                controles.paso(3, "Revisar destino",
                               "Define la atribución, el nombre de la carpeta y el destino."),
                ft.Text("Atribución y nombres", size=13, weight=ft.FontWeight.W_600),
                ft.ResponsiveRow(
                    controls=[self.campo_creador, self.campo_coleccion,
                              self.campo_prefijo, self.campo_credito],
                    spacing=12, run_spacing=12,
                ),
                ft.ExpansionTile(
                    title=ft.Text("Atribución por carpeta", size=13),
                    subtitle=ft.Text("Ajusta el creador o la colección de una carpeta concreta.", size=12),
                    controls=[self._bloque_reglas()],
                ),
                ft.ExpansionTile(
                    title=ft.Text("Opciones avanzadas", size=13),
                    subtitle=ft.Text("Transformaciones del nombre y medios externos.", size=12),
                    controls=[
                        ft.Column(
                            controls=[
                                self.campo_avanzado_quitar,
                                self.campo_avanzado_guiones,
                                self.campo_avanzado_mayusculas,
                                self.campo_avanzado_medios,
                            ],
                            spacing=8,
                        )
                    ],
                ),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.Text("Destino", size=13, weight=ft.FontWeight.W_600),
                ft.Row(
                    controls=[
                        ft.Button(content="Elegir carpeta…", icon=ft.Icons.FOLDER_OPEN,
                                  on_click=self.elegir_carpeta_destino),
                        self.campo_destino,
                    ],
                    spacing=10,
                ),
                ft.ResponsiveRow(
                    controls=[
                        self.campo_nombre_carpeta,
                        ft.Container(content=self.casilla_paquete, col={"xs": 12, "md": 12}),
                    ],
                    spacing=12, run_spacing=12,
                ),
                ft.Row(
                    controls=[
                        self.boton_elegir_paquete,
                        self.campo_paquete,
                    ],
                    spacing=10,
                ),
                self.texto_destino,
                ft.Text("Vista previa de nombres y carpetas", size=13, weight=ft.FontWeight.W_600),
                self.lista_previa,
                self.mensaje_previa,
            ],
            spacing=10,
        )
        self.seccion_destino.visible = True

    def _bloque_reglas(self) -> ft.Column:
        self.campos_regla = {}
        bloques = []
        for carpeta in self.inventario.carpetas:
            regla = self.reglas.get(carpeta) or ReglaCarpeta(carpeta=carpeta)
            campos = {
                "creador": ft.TextField(label="Creador", value=regla.creador, dense=True),
                "coleccion": ft.TextField(label="Colección", value=regla.coleccion, dense=True),
                "credito": ft.TextField(label="Crédito", value=regla.credito, dense=True),
                "subcarpeta": ft.TextField(label="Subcarpeta", value=regla.subcarpeta, dense=True),
            }
            sin_subcarpeta = ft.Checkbox(label="Sin nivel de subcarpeta", value=regla.sin_subcarpeta)
            campos["sin_subcarpeta"] = sin_subcarpeta
            self.campos_regla[carpeta] = campos
            bloques.append(ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(carpeta, size=13, weight=ft.FontWeight.W_600),
                        ft.ResponsiveRow(
                            controls=[campos["creador"], campos["coleccion"],
                                      campos["credito"], campos["subcarpeta"]],
                            spacing=10, run_spacing=10,
                        ),
                        sin_subcarpeta,
                    ],
                    spacing=6,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                border_radius=RADIO,
            ))
        return ft.Column(controls=bloques, spacing=8)

    def leer_reglas(self) -> None:
        for carpeta, campos in self.campos_regla.items():
            self.reglas[carpeta] = ReglaCarpeta(
                carpeta=carpeta,
                creador=campos["creador"].value or "",
                coleccion=campos["coleccion"].value or "",
                credito=campos["credito"].value or "",
                subcarpeta=campos["subcarpeta"].value or "",
                sin_subcarpeta=bool(campos["sin_subcarpeta"].value),
            )

    async def elegir_carpeta_destino(self, evento) -> None:
        carpeta = await self.selector.get_directory_path(
            dialog_title="Elige dónde crear la carpeta de la exportación")
        if not carpeta:
            return
        self.carpeta_destino = Path(carpeta)
        self.campo_destino.value = carpeta
        refrescar(self.campo_destino)
        self.actualizar_previsualizacion()

    async def elegir_ruta_paquete(self, evento) -> None:
        ruta = await self.selector.save_file(
            dialog_title="Guardar el paquete .drfx",
            file_name=f"{self.nombre_carpeta}.drfx",
            allowed_extensions=["drfx"],
        )
        if not ruta:
            return
        self.ruta_paquete_manual = Path(ruta)
        self.actualizar_previsualizacion()

    def al_cambiar_paquete(self, evento) -> None:
        self.crear_paquete = bool(evento.control.value)
        self.actualizar_previsualizacion()

    def al_cambiar_nombres(self, evento) -> None:
        self.opciones.creador = self.campo_creador.value or ""
        self.opciones.coleccion = self.campo_coleccion.value or ""
        self.opciones.prefijo = self.campo_prefijo.value or ""
        self.opciones.credito = self.campo_credito.value or ""
        self.opciones.quitar_prefijo = self.campo_avanzado_quitar.value or ""
        self.opciones.guiones_a_espacios = bool(self.campo_avanzado_guiones.value)
        self.opciones.mayusculas_iniciales = bool(self.campo_avanzado_mayusculas.value)
        self.opciones.permitir_medios_externos = bool(self.campo_avanzado_medios.value)
        self.nombre_carpeta = self.campo_nombre_carpeta.value or ""
        self.leer_reglas()
        self.actualizar_previsualizacion()

    # ----------------------------------------------------------------- #
    # Vista previa y validación
    # ----------------------------------------------------------------- #

    def composiciones_seleccionadas(self) -> list[ComposicionInfo]:
        return [info for info in self.inventario.composiciones if info.clave in self.seleccion]

    def ruta_paquete_propuesta(self) -> Path | None:
        if self.ruta_paquete_manual:
            return self.ruta_paquete_manual
        if self.carpeta_destino and self.nombre_carpeta.strip():
            return self.carpeta_destino / f"{self.nombre_carpeta.strip()}.drfx"
        return None

    def actualizar_previsualizacion(self) -> None:
        if not hasattr(self, "lista_previa"):
            return
        destino, problemas_destino = comprobar_destino(self.carpeta_destino, self.nombre_carpeta)
        self.texto_destino.value = f"Se creará: {destino}" if destino else "Indica una carpeta de destino y un nombre nuevo."
        refrescar(self.texto_destino)

        self.campo_paquete.visible = self.crear_paquete
        self.boton_elegir_paquete.visible = self.crear_paquete
        ruta_paquete = self.ruta_paquete_propuesta()
        if self.crear_paquete:
            self.campo_paquete.value = str(ruta_paquete) if ruta_paquete else ""
            if ruta_paquete and ruta_paquete.exists():
                problemas_destino.append(
                    f"Ya existe «{ruta_paquete.name}». Elige otro nombre: no se sobrescribe nada.")
        refrescar(self.campo_paquete)
        refrescar(self.boton_elegir_paquete)

        seleccion = self.composiciones_seleccionadas()
        config = construir_config(self.opciones, self.reglas.values())
        previsiones = previsualizar(seleccion, config)
        filas = []
        for prevision in previsiones:
            if prevision.error:
                filas.append(ft.Text(f"{prevision.carpeta}/{prevision.nombre}: {prevision.error}",
                                     size=12, color=COLOR_ERROR))
            else:
                filas.append(ft.Text(f"{prevision.carpeta}/{prevision.nombre} → {prevision.ruta}",
                                     size=12, color=COLOR_TENUE))
        if not filas:
            filas.append(ft.Text("Selecciona alguna composición para ver el resultado.", size=12, color=COLOR_TENUE))
        self.lista_previa.controls = filas
        refrescar(self.lista_previa)

        conflictos = rutas_en_conflicto(previsiones)
        mensajes = list(problemas_destino)
        for ruta, titulos in conflictos:
            mensajes.append(
                f"Dos títulos usarían la misma ruta ({ruta}): {', '.join(titulos)}. "
                "Cambia el nombre, el creador o la colección.")
        con_medios = [info for info in seleccion
                      if info.medios and not self.opciones.permitir_medios_externos]
        if con_medios:
            mensajes.append(
                f"{len(con_medios)} título(s) usan medios externos. Activa «Permitir títulos que usan "
                "medios externos» en las opciones avanzadas o no se exportarán.")
        if mensajes:
            self.mensaje_previa.content = controles.mensaje("\n".join(mensajes), tono="aviso")
            self.mensaje_previa.visible = True
        else:
            self.mensaje_previa.visible = False
            self.mensaje_previa.content = None
        refrescar(self.mensaje_previa)

        listo = bool(seleccion) and destino is not None and not problemas_destino \
            and not conflictos and not con_medios
        self.boton_exportar.disabled = not listo
        self.estado.value = self._estado_pendiente(seleccion, destino, problemas_destino,
                                                    conflictos, con_medios)
        refrescar(self.boton_exportar)
        refrescar(self.estado)

    @staticmethod
    def _estado_pendiente(seleccion, destino, problemas_destino, conflictos, con_medios) -> str:
        """Explica qué falta para poder exportar, en una sola frase."""
        if not seleccion:
            return "Selecciona las composiciones que quieres exportar."
        if destino is None:
            return "Elige una carpeta de destino y un nombre de carpeta nuevo."
        if problemas_destino:
            return problemas_destino[0]
        if conflictos:
            return "Dos títulos usarían la misma ruta: cambia el nombre o la atribución."
        if con_medios:
            return "Hay títulos con medios externos: actívalos en las opciones avanzadas."
        return "Listo para exportar."

    # ----------------------------------------------------------------- #
    # Ejecución
    # ----------------------------------------------------------------- #

    async def exportar(self, evento) -> None:
        if self.boton_exportar.disabled:
            return
        destino, problemas = comprobar_destino(self.carpeta_destino, self.nombre_carpeta)
        if destino is None or problemas:
            await self.mostrar_resultado_error(problemas[0] if problemas else "Revisa el destino.")
            return
        seleccion = {info.clave for info in self.composiciones_seleccionadas()}
        config = construir_config(self.opciones, self.reglas.values())
        ruta_paquete = self.ruta_paquete_propuesta()
        if self.crear_paquete:
            if ruta_paquete is None:
                await self.mostrar_resultado_error("Elige dónde guardar el paquete .drfx.")
                return
            if ruta_paquete.exists():
                await self.mostrar_resultado_error(
                    f"Ya existe «{ruta_paquete.name}». Elige otro nombre: no se sobrescribe nada.")
                return

        self.boton_exportar.disabled = True
        self.barra_progreso.visible = True
        self.barra_progreso.value = 0
        self.texto_progreso.visible = True
        self.texto_progreso.value = "Preparando…"
        self.estado.value = "Exportando títulos…"
        self.fila_resultado.visible = False
        refrescar(self.fila_resultado)
        refrescar(self.barra_progreso)
        refrescar(self.texto_progreso)
        refrescar(self.estado)

        self.cola = queue.Queue()

        def progreso(hechos: int, total: int, mensaje: str) -> None:
            self.cola.put(("avance", hechos, total, mensaje))

        def trabajo() -> None:
            try:
                resultado = exportar_titulos(
                    self.inventario.origen, destino, seleccion, config,
                    permitir_medios=self.opciones.permitir_medios_externos, progreso=progreso)
                self.cola.put(("fin", resultado, None))
            except Exception as exc:  # noqa: BLE001 - el error se muestra a la persona
                self.cola.put(("fin", None, exc))

        threading.Thread(target=trabajo, daemon=True).start()
        await self._esperar()
        self.actualizar_previsualizacion()

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
            if error is not None:
                mensaje, pista = explicar_error(error)
                await self.mostrar_resultado_error(mensaje, pista)
                self.barra_progreso.visible = False
                self.texto_progreso.visible = False
                self.estado.value = "La exportación no se completó."
                refrescar(self.barra_progreso)
                refrescar(self.texto_progreso)
                refrescar(self.estado)
                return
            await self._finalizar(resultado)
            return

    async def _finalizar(self, resultado: ResultadoExportacion) -> None:
        self.barra_progreso.visible = False
        self.texto_progreso.visible = False
        refrescar(self.barra_progreso)
        refrescar(self.texto_progreso)
        self.estado.value = "Exportación completada."
        refrescar(self.estado)
        avisos = []
        if resultado.fuentes:
            avisos.append(f"Fuentes declaradas, no se comprueba que estén instaladas: {', '.join(resultado.fuentes)}.")
        if resultado.medios:
            avisos.append(f"Medios externos conservados solo como referencia: {', '.join(resultado.medios)}.")
        avisos.append("La conversión no comprueba el render ni los botones personalizados del Inspector.")
        await self.mostrar_resultado_exito(resultado, avisos)

    # ----------------------------------------------------------------- #
    # Resultado
    # ----------------------------------------------------------------- #

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

    async def mostrar_resultado_exito(self, resultado: ResultadoExportacion,
                                     avisos: list[str]) -> None:
        async def consultar_informe(evento) -> None:
            await self._mostrar_informe(resultado)

        # La barra fija resume el resultado y da acceso a la carpeta y al informe.
        self.fila_resultado.controls = [
            ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLOR_OK, size=18),
            ft.Text(f"{resultado.titulos} títulos exportados en {resultado.carpeta}",
                    size=13, color=COLOR_OK, expand=True),
            ft.Button(content="Abrir carpeta", icon=ft.Icons.FOLDER_OPEN,
                      on_click=lambda e: abrir_en_el_sistema(resultado.carpeta)),
            ft.Button(content="Consultar informe", icon=ft.Icons.DESCRIPTION,
                      on_click=consultar_informe),
        ]
        self.fila_resultado.visible = True
        refrescar(self.fila_resultado)

        piezas = [
            ft.Text(f"{resultado.titulos} títulos exportados.", size=14, weight=ft.FontWeight.W_600,
                    color=COLOR_OK),
            controles.ruta_texto(str(resultado.carpeta)),
        ]
        if avisos:
            piezas.append(ft.Column(
                controls=[ft.Text(aviso, size=12, color=COLOR_TENUE) for aviso in avisos],
                spacing=2,
            ))
        piezas.append(ft.Row(
            controls=[
                ft.Button(content="Abrir carpeta", icon=ft.Icons.FOLDER_OPEN,
                          on_click=lambda e: abrir_en_el_sistema(resultado.carpeta)),
                ft.Button(content="Consultar informe", icon=ft.Icons.DESCRIPTION,
                          on_click=consultar_informe),
            ],
            spacing=10,
        ))
        self.panel_resultado.content = ft.Container(
            content=ft.Column(controls=piezas, spacing=8),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=RADIO,
            border=ft.Border(left=ft.BorderSide(3, COLOR_OK)),
        )
        self.panel_resultado.visible = True
        refrescar(self.panel_resultado)

    async def _mostrar_informe(self, resultado: ResultadoExportacion) -> None:
        try:
            contenido = resultado.ruta_manifiesto.read_text(encoding="utf-8")
        except OSError as exc:
            await self.mostrar_resultado_error("No se pudo leer el informe.", str(exc))
            return
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Informe de la exportación"),
            content=ft.Container(
                content=ft.ListView(
                    controls=[ft.Text(contenido, size=11, selectable=True, font_family="Consolas")],
                    expand=True,
                ),
                height=420, width=620,
            ),
            actions=[
                ft.Button(content="Abrir con el sistema",
                          on_click=lambda e: abrir_en_el_sistema(resultado.ruta_manifiesto)),
                ft.Button(content="Cerrar", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)
