"""Pruebas del motor: conversion de composiciones y empaquetado DRFX.

El motor esta dividido en modulos pequenos dentro de ``src/davinci_exportador``.
Aqui se comprueban los limites de seguridad: no se sobrescribe nada, no se
publica una exportacion parcial y no se ejecutan las expresiones del origen.
"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from davinci_exportador import conversion, empaquetado  # noqa: E402
from davinci_exportador.errores import ExportError  # noqa: E402
from davinci_exportador.fusion import entries, table_end  # noqa: E402
from davinci_exportador.modelo import Composition  # noqa: E402

GRAPH = '''{
Template = TextPlus { Inputs = { StyledText = Input { Value = "Hola", },
  Font = Input { Value = "Fuente de prueba", },
  Size = Input { Expression = "iif(time > 4, .1, .2)", }, },
  UserControls = ordered() { MiColor = { INPID_InputControl = "ColorControl", }, }, },
MediaOut1 = MediaOut { Inputs = { Input = Input { SourceOp = "Template", Source = "Output", }, }, },
}'''


class ExportSafetyTests(unittest.TestCase):
    def test_preserves_graph_and_animation_expression(self):
        comp = Composition("Estilos", "Saludo", "fixture", "", GRAPH)
        setting, metadata = conversion.make_title(comp)
        source_node = entries(GRAPH)[0].text
        self.assertIn(source_node, setting)
        self.assertIn('iif(time > 4, .1, .2)', setting)
        self.assertIn("MiColor", metadata["controls"])
        self.assertNotIn("MediaOut1 = MediaOut", setting)

    def test_tables_ignore_braces_inside_strings_and_long_strings(self):
        text = '{ Value = "}", Script = [=[ { do not execute } ]=], Nested = { A = 1 } } trailing'
        self.assertEqual(text[table_end(text, 0):], " trailing")

    def test_existing_output_is_not_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "resultado"
            destination.mkdir()
            sentinel = destination / "trabajo.txt"
            sentinel.write_text("conservar", encoding="utf-8")
            with self.assertRaises(ExportError):
                conversion.export_titles(root / "no-existe.drb", destination)
            self.assertEqual(sentinel.read_text(), "conservar")

    def test_collision_does_not_publish_partial_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "entrada.drb"
            # Real collision is caused by Windows-invalid characters sanitizing
            # to the same filename, before any output folder is committed.
            original_reader = conversion.read_compositions
            conversion.read_compositions = lambda _: [
                Composition("A", "Uno:Dos", "fixture", "", GRAPH),
                Composition("A", "Uno?Dos", "fixture", "", GRAPH),
            ]
            try:
                with self.assertRaises(ExportError):
                    conversion.export_titles(source, root / "salida")
            finally:
                conversion.read_compositions = original_reader
            self.assertFalse((root / "salida").exists())

    def test_external_media_rejected_without_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "entrada.comp"
            graph = GRAPH[:-1] + ', Imagen = Loader { Clips = {} }, }'
            source.write_text("Composition { Tools = ordered() " + graph + " }", encoding="utf-8")
            with self.assertRaises(ExportError):
                conversion.export_titles(source, root / "salida")
            self.assertFalse((root / "salida").exists())

    def test_package_keeps_assets_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Templates"
            category = source / "Edit/Titles/Autor"
            category.mkdir(parents=True)
            (category / "Prueba.setting").write_text("{}")
            (category / "icono.png").write_bytes(b"recurso original")
            output = root / "paquete.drfx"
            empaquetado.package_templates(source, output)
            with zipfile.ZipFile(output) as package:
                self.assertEqual(package.read("Edit/Titles/Autor/icono.png"), b"recurso original")
            previous = output.read_bytes()
            with self.assertRaises(ExportError):
                empaquetado.package_templates(source, output)
            self.assertEqual(output.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
