"""Pruebas de la capa de servicio de la interfaz.

Comprueban la preparación de la exportación —qué se puede exportar, cómo se
nombrará y a dónde se escribe— sin abrir la ventana.
"""

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import auxiliares  # noqa: E402
from davinci_exportador.controller import (  # noqa: E402
    comprobar_plantillas,
    empaquetar_plantillas,
    explicar_error,
    exportar_titulos,
)
from davinci_exportador.errores import ExportError  # noqa: E402
from davinci_exportador.inventario import ComposicionInfo, inventariar  # noqa: E402
from davinci_exportador.reglas import (  # noqa: E402
    OpcionesNombres,
    ReglaCarpeta,
    comprobar_destino,
    comprobar_salida_paquete,
    construir_config,
    previsualizar,
    rutas_en_conflicto,
)


def _carpeta_principal(path: Path) -> str:
    return "Edit/Titles/Autor/Coleccion"


class InventarioTests(unittest.TestCase):
    def test_lista_carpetas_y_explica_los_problemas(self):
        with tempfile.TemporaryDirectory() as temporal:
            origen = auxiliares.crear_drb(Path(temporal) / "bandeja.drb", {
                "Titulos": [("Uno", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)])],
                "Adaptaciones": [
                    ("Original", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)]),
                    ("Duplicado", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO),
                                   auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)]),
                    ("Sin salida", [auxiliares.composition_ba(auxiliares.GRAFO_DOS_TEXTOS)]),
                ],
            })
            inventario = inventariar(origen)

        self.assertIsNone(inventario.error)
        self.assertEqual(inventario.carpetas, ["Titulos", "Adaptaciones"])
        compatibles = [c for c in inventario.composiciones if c.compatible]
        self.assertEqual(len(compatibles), 2)
        incompatibles = [c for c in inventario.composiciones if not c.compatible]
        self.assertEqual(len(incompatibles), 1)
        self.assertIn("TextPlus", incompatibles[0].motivo)
        # El generador con dos composiciones se avisa, pero no oculta el resto.
        self.assertEqual(len(inventario.problemas), 1)
        self.assertIn("Adaptaciones/Duplicado", inventario.problemas[0])

    def test_archivo_no_admitido_explica_el_error(self):
        with tempfile.TemporaryDirectory() as temporal:
            origen = Path(temporal) / "video.mp4"
            origen.write_bytes(b"contenido")
            inventario = inventariar(origen)
        self.assertIsNotNone(inventario.error)
        self.assertIn(".drb", inventario.error)

    def test_registra_fuentes_y_medios_pendientes(self):
        with tempfile.TemporaryDirectory() as temporal:
            origen = auxiliares.crear_drb(Path(temporal) / "bandeja.drb", {
                "Titulos": [("Uno", [auxiliares.composition_ba(auxiliares.GRAFO_CON_MEDIOS)])],
            })
            inventario = inventariar(origen)
        info = inventario.composiciones[0]
        self.assertTrue(info.compatible)
        self.assertEqual(info.medios, ("Imagen",))
        self.assertEqual(info.fuentes, ())

    def test_registra_las_fuentes_declaradas(self):
        with tempfile.TemporaryDirectory() as temporal:
            origen = auxiliares.crear_drb(Path(temporal) / "bandeja.drb", {
                "Titulos": [("Uno", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)])],
            })
            inventario = inventariar(origen)
        self.assertEqual(inventario.composiciones[0].fuentes, ("Fuente de prueba",))


class ReglasDeNombresTests(unittest.TestCase):
    def test_los_campos_vacios_heredan_el_valor_general(self):
        opciones = OpcionesNombres(creador="Orson Lord", coleccion="Subtitulos",
                                             credito="OL")
        reglas = [ReglaCarpeta(carpeta="biglexj", creador="Biglex J")]
        config = construir_config(opciones, reglas)

        self.assertEqual(config["defaults"]["creator"], "Orson Lord")
        self.assertEqual(config["defaults"]["credit"], "OL")
        self.assertEqual(len(config["rules"]), 1)
        self.assertEqual(config["rules"][0], {"folder": "biglexj", "creator": "Biglex J"})

    def test_una_carpeta_sin_ajustes_no_genera_regla(self):
        config = construir_config(
            OpcionesNombres(creador="Orson Lord"),
            [ReglaCarpeta(carpeta="Titulos")],
        )
        self.assertEqual(config["rules"], [])

    def test_la_previsualizacion_usa_las_reglas_por_carpeta(self):
        opciones = OpcionesNombres(creador="Orson Lord", coleccion="Subtitulos")
        config = construir_config(
            opciones,
            [ReglaCarpeta(carpeta="Adaptaciones", creador="Biglex J",
                                    subcarpeta="v2", sin_subcarpeta=False)],
        )
        composiciones = [
            ComposicionInfo("Titulos", "Uno", "x", True),
            ComposicionInfo("Adaptaciones", "Dos", "x", True),
        ]
        previsiones = previsualizar(composiciones, config)
        self.assertIn("Orson Lord", previsiones[0].ruta)
        self.assertIn("Biglex J", previsiones[1].ruta)
        self.assertIn("v2", previsiones[1].ruta)

    def test_detecta_los_titulos_que_terminan_en_la_misma_ruta(self):
        composiciones = [
            ComposicionInfo("A", "Uno:Dos", "x", True),
            ComposicionInfo("A", "Uno?Dos", "x", True),
        ]
        config = construir_config(OpcionesNombres(creador="Autor"), [])
        previsiones = previsualizar(composiciones, config)
        conflictos = rutas_en_conflicto(previsiones)
        self.assertEqual(len(conflictos), 1)
        self.assertEqual(len(conflictos[0][1]), 2)


class DestinoTests(unittest.TestCase):
    def test_rechaza_un_nombre_de_carpeta_invalido(self):
        with tempfile.TemporaryDirectory() as temporal:
            destino, problemas = comprobar_destino(Path(temporal), "titulos/malos")
        self.assertIsNone(destino)
        self.assertTrue(problemas)

    def test_avisa_si_la_carpeta_ya_existe(self):
        with tempfile.TemporaryDirectory() as temporal:
            (Path(temporal) / "titulos").mkdir()
            destino, problemas = comprobar_destino(Path(temporal), "titulos")
        self.assertIsNotNone(destino)
        self.assertTrue(problemas)
        self.assertIn("ya existe", problemas[0].lower())

    def test_una_carpeta_nueva_no_tiene_problemas(self):
        with tempfile.TemporaryDirectory() as temporal:
            destino, problemas = comprobar_destino(Path(temporal), "titulos")
        self.assertEqual(problemas, [])
        self.assertEqual(destino.name, "titulos")

    def test_el_paquete_gana_la_extension_y_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal)
            salida, problemas = comprobar_salida_paquete(base, "paquete")
            self.assertEqual(problemas, [])
            self.assertEqual(salida.name, "paquete.drfx")
            salida.write_bytes(b"contenido")
            salida, problemas = comprobar_salida_paquete(base, "paquete")
            self.assertTrue(problemas)


class ExportacionTests(unittest.TestCase):
    def _origen(self, raiz: Path) -> Path:
        return auxiliares.crear_drb(raiz / "bandeja.drb", {
            "Titulos": [
                ("Uno", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)]),
                ("Dos", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)]),
            ],
            "Adaptaciones": [
                ("Tres", [auxiliares.composition_ba(auxiliares.GRAFO_VALIDO)]),
            ],
        })

    def test_exporta_solo_los_titulos_seleccionados(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            origen = self._origen(raiz)
            destino = raiz / "salida"
            opciones = OpcionesNombres(creador="Orson Lord", coleccion="Subtitulos")
            config = construir_config(opciones, [])
            seleccion = {("Titulos", "Uno"), ("Adaptaciones", "Tres")}

            resultado = exportar_titulos(origen, destino, seleccion, config)

            self.assertEqual(resultado.titulos, 2)
            archivos = sorted(p.name for p in (destino / "Templates").rglob("*.setting"))
            self.assertEqual(archivos, ["Tres.setting", "Uno.setting"])
            manifiesto = json.loads((destino / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifiesto["titles"]), 2)
            self.assertFalse(manifiesto["native_render_verified"])

    def test_el_destino_existente_no_se_toca(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            origen = self._origen(raiz)
            destino = raiz / "salida"
            destino.mkdir()
            (destino / "trabajo.txt").write_text("conservar", encoding="utf-8")
            config = construir_config(OpcionesNombres(creador="Autor"), [])

            with self.assertRaises(ExportError):
                exportar_titulos(origen, destino, {("Titulos", "Uno")}, config)

            self.assertEqual((destino / "trabajo.txt").read_text(encoding="utf-8"), "conservar")
            self.assertFalse((destino / "Templates").exists())

    def test_el_avance_usa_datos_reales(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            origen = self._origen(raiz)
            destino = raiz / "salida"
            config = construir_config(OpcionesNombres(creador="Autor"), [])
            avances = []

            exportar_titulos(
                origen, destino, {("Titulos", "Uno"), ("Titulos", "Dos")}, config,
                progreso=lambda hechos, total, mensaje: avances.append((hechos, total, mensaje)))

        self.assertTrue(avances)
        self.assertEqual(avances[-1][0], 2)
        self.assertEqual(avances[-1][1], 2)

    def test_los_titulos_con_medios_externos_se_rechazan_sin_dejar_rastro(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            origen = auxiliares.crear_drb(raiz / "bandeja.drb", {
                "Titulos": [("Uno", [auxiliares.composition_ba(auxiliares.GRAFO_CON_MEDIOS)])],
            })
            destino = raiz / "salida"
            config = construir_config(OpcionesNombres(creador="Autor"), [])

            with self.assertRaises(ExportError):
                exportar_titulos(origen, destino, {("Titulos", "Uno")}, config)
            self.assertFalse(destino.exists())

            permitido = exportar_titulos(
                origen, raiz / "salida2", {("Titulos", "Uno")}, config, permitir_medios=True)
            self.assertEqual(permitido.titulos, 1)
            self.assertEqual(permitido.medios, ["Imagen"])


class EmpaquetadoTests(unittest.TestCase):
    def _carpeta_plantillas(self, raiz: Path) -> Path:
        origen = raiz / "Templates"
        categoria = origen / "Edit/Titles/Autor/Coleccion"
        categoria.mkdir(parents=True)
        (categoria / "Prueba.setting").write_text("{}", encoding="utf-8")
        (categoria / "icono.png").write_bytes(b"recurso original")
        return origen

    def test_comprueba_la_estructura_sin_escribir(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            carpeta = self._carpeta_plantillas(raiz)
            informe, error = comprobar_plantillas(carpeta)
            self.assertIsNone(error)
            self.assertEqual(informe["settings"], 1)
            self.assertEqual(informe["resources"], 1)
            self.assertEqual(informe["categories"], ["Titles"])
            self.assertEqual(informe["categories_summary"], {"Titles": 1})
            self.assertEqual(len(informe["templates"]), 1)
            self.assertEqual(informe["templates"][0]["name"], "Prueba")
            self.assertEqual(informe["templates"][0]["category"], "Titles")

    def test_explica_una_carpeta_sin_estructura_valida(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            carpeta = raiz / "cualquier"
            carpeta.mkdir()
            informe, error = comprobar_plantillas(carpeta)
            self.assertIsNone(informe)
            self.assertIn(".setting", error)

    def test_crea_el_paquete_y_lo_verifica(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            carpeta = self._carpeta_plantillas(raiz)
            salida = raiz / "paquete.drfx"
            meta = {"author": "Biglex J", "version": "1.2.0"}
            resultado = empaquetar_plantillas(carpeta, salida, metadata=meta)

            self.assertEqual(resultado.titulos, 1)
            self.assertEqual(resultado.archivos, 2)
            self.assertEqual(resultado.metadata.get("author"), "Biglex J")
            self.assertEqual(resultado.metadata.get("version"), "1.2.0")
            with zipfile.ZipFile(resultado.paquete) as paquete:
                self.assertIn("Edit/Titles/Autor/Coleccion/icono.png", paquete.namelist())
                self.assertIsNone(paquete.testzip())


class MensajesTests(unittest.TestCase):
    def test_los_errores_conocidos_explican_cmo_resolverlos(self):
        mensaje, pista = explicar_error(
            ExportError("La carpeta de salida ya existe; no se sobrescribe ni mezcla contenido."))
        self.assertIn("ya existe", mensaje.lower())
        self.assertTrue(pista)

    def test_un_error_desconocido_conserva_el_mensaje_original(self):
        mensaje, pista = explicar_error(ExportError("Algo raro ha pasado"))
        self.assertEqual(mensaje, "Algo raro ha pasado")
        self.assertEqual(pista, "")


if __name__ == "__main__":
    unittest.main()
