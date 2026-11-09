; ---------------------------------------------------------------------------
; identity.iss - identidad de DaVinci Exportador para el instalador de Windows.
; Mantener MyAppId estable entre versiones: es la clave de actualizacion.
; ---------------------------------------------------------------------------

; Nombre visible de la aplicacion (el que ve el usuario en el titulo del
; asistente y en el menu de inicio).
#ifndef MyAppName
  #define MyAppName "DaVinci Exportador"
#endif

; Identidad de actualizacion, propia y estable de DaVinci Exportador.
; GUID generado para este proyecto; no reutilizar el de la plantilla ni el de
; ninguna otra app de Biglex.
#ifndef MyAppId
  #define MyAppId "{00F8CBCD-E4EB-462E-9B6A-7C48BD67C1A8}"
#endif

; Carpeta de instalacion: {localappdata}\Programs\DaVinciExportador
#ifndef MyAppDirectory
  #define MyAppDirectory "DaVinciExportador"
#endif

; Ejecutable real del artefacto de escritorio (PyInstaller, modo onedir).
#ifndef MyAppExe
  #define MyAppExe "DaVinciExportador.exe"
#endif

; Icono oficial de la aplicacion (copia de
; assets\branding\icons\icon-windows.ico, con transparencia y 256x256).
#ifndef MyAppIcon
  #define MyAppIcon "DaVinciExportador.ico"
#endif

; Tema automatico: claro u oscuro segun el de Windows.
#ifndef MyAppTheme
  #define MyAppTheme "dynamic"
#endif

; Carpeta con el artefacto de escritorio empaquetado, relativa a esta carpeta.
; La prepara scripts/packaging/Build-Installer.ps1 (salida onedir de
; PyInstaller, recreada limpia en cada compilacion).
#ifndef MyAppPayload
  #define MyAppPayload "build\dist\DaVinciExportador"
#endif

#ifndef MyAppSubtitle
  #define MyAppSubtitle "De Fusion a plantillas de Resolve."
#endif
