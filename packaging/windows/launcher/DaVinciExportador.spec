# -*- mode: python ; coding: utf-8 -*-
"""Especificacion de PyInstaller para el ejecutable de DaVinci Exportador.

La consume `scripts/packaging/Build-Installer.ps1`. El bundle es
autocontenido: ademas del codigo de la app incluye el cliente de escritorio
de Flet, para que la primera ejecucion no dependa de una descarga.

Salida: un directorio `DaVinciExportador/` con `DaVinciExportador.exe` y
`_internal/`. Se instala completo en `{app}`.
"""

import os
import tomllib
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
WINDOWS_DIR = SPEC_DIR.parent
ROOT = WINDOWS_DIR.parent.parent
BUILD_DIR = WINDOWS_DIR / "build"
CLIENT_ZIP = BUILD_DIR / "cache" / "flet-windows.zip"
LAUNCHER = SPEC_DIR / "DaVinciExportador.py"
ICON = ROOT / "assets" / "branding" / "icons" / "icon-windows.ico"

if not CLIENT_ZIP.is_file():
    raise SystemExit(
        "Falta el cliente de escritorio de Flet (%s). Ejecuta "
        "scripts/packaging/Build-Installer.ps1 para preparar el staging."
        % CLIENT_ZIP
    )

# --- Version real leida de pyproject.toml -----------------------------------
with (ROOT / "pyproject.toml").open("rb") as handle:
    _version = tomllib.load(handle)["project"]["version"]
_version_tuple = tuple(int(part) for part in _version.split("."))
while len(_version_tuple) < 4:
    _version_tuple = _version_tuple + (0,)

BUILD_DIR.mkdir(parents=True, exist_ok=True)
VERSION_FILE = BUILD_DIR / "version_info.txt"
VERSION_FILE.write_text(
    """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=%s,
    prodvers=%s,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Biglex'),
         StringStruct('FileDescription', 'DaVinci Exportador'),
         StringStruct('FileVersion', '%s'),
         StringStruct('InternalName', 'DaVinciExportador'),
         StringStruct('OriginalFilename', 'DaVinciExportador.exe'),
         StringStruct('ProductName', 'DaVinci Exportador'),
         StringStruct('ProductVersion', '%s')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    % (
        _version_tuple,
        _version_tuple,
        _version,
        _version,
    ),
    encoding="utf-8",
)

datas = [
    (str(ROOT / "assets" / "branding" / "icons"), "assets/branding/icons"),
    (str(CLIENT_ZIP), "flet_desktop/app"),
]
binaries = []
hiddenimports = []

# Flet distribuye datos (icons.json, assets, plantillas) que se leen en
# tiempo de ejecucion: sin `collect_all` el cliente no encuentra sus
# archivos y la app falla al construir la interfaz.
from PyInstaller.utils.hooks import collect_all

for _package in ("flet", "flet_desktop"):
    _datas, _binaries, _hidden = collect_all(_package)
    datas += _datas
    binaries += _binaries
    hiddenimports += _hidden

a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(ROOT / "src"), str(ROOT / "src-flet")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "pydoc_data"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DaVinciExportador",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=os.environ.get("DAVINCIEXPORTADOR_DEBUG_CONSOLE") == "1",
    disable_windowed_traceback=False,
    icon=str(ICON),
    version=str(VERSION_FILE),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DaVinciExportador",
)
