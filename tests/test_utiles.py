"""Pruebas de las utilidades del motor."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from davinci_exportador.utiles import renombrar_con_reintentos  # noqa: E402


class RenombradoTests(unittest.TestCase):
    def test_publica_el_contenido_preparado(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            preparado = raiz / "preparado"
            preparado.mkdir()
            (preparado / "archivo.txt").write_text("contenido", encoding="utf-8")
            destino = raiz / "publicado"

            renombrar_con_reintentos(preparado, destino)

            self.assertTrue((destino / "archivo.txt").is_file())
            self.assertFalse(preparado.exists())

    def test_reintenta_cuando_windows_bloquea_el_movimiento(self):
        """El antivirus puede bloquear un instante lo recién escrito."""
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            preparado = raiz / "preparado"
            preparado.mkdir()
            destino = raiz / "publicado"
            original = Path.rename
            intentos = {"cuenta": 0}

            def rename_bloqueado(self, target):
                if self == preparado and intentos["cuenta"] == 0:
                    intentos["cuenta"] += 1
                    raise PermissionError(5, "Acceso denegado")
                return original(self, target)

            Path.rename = rename_bloqueado
            try:
                renombrar_con_reintentos(preparado, destino)
            finally:
                Path.rename = original

            self.assertEqual(intentos["cuenta"], 1)
            self.assertTrue(destino.is_dir())


if __name__ == "__main__":
    unittest.main()
