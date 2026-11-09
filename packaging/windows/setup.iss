; ============================================================================
; setup.iss  -  Instalador de Windows de DaVinci Exportador (Biglex Modern 2.0)
; ----------------------------------------------------------------------------
; Basado en la plantilla compartida "Biglex Modern 2.0".
; Copia autocontenida: este repositorio no referencia la carpeta compartida.
;
; Pantallas: entrada -> progreso -> exito. Sin bienvenida, sin licencia, sin
; grupo de programa y sin "listo para instalar".
;
; version.iss lo regenera scripts/packaging/Build-Installer.ps1 con la version
; real leida de pyproject.toml.
;
; Compilar:
;   & "..\..\..\Scripts\tools\InnoSetup\ISCC.exe" setup.iss
; (o usa la tarea de Mise: mise release)
; ============================================================================

#include "version.iss"
#include "identity.iss"

[Setup]
; --- IDENTIDAD DE ACTUALIZACION: unica y estable por app -------------------
; Mantenerla para que una version nueva actualice la anterior y no cree una
; instalacion paralela. No existe un instalador previo de DaVinci Exportador:
; esta identidad es propia y nace con este instalador.
;
; Doble llave SOLO en la apertura: identity.iss guarda el GUID entre llaves,
; asi que hace falta la forma `{{#MyAppId}` para que Inno Setup lo interprete
; como texto literal y no como una constante de la seccion [Setup].
AppId={{#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Biglex
AppPublisherURL=https://biglexj.com
AppSupportURL=https://biglexj.com
DefaultDirName={localappdata}\Programs\{#MyAppDirectory}
DefaultGroupName={#MyAppName}
; --- Pantallas: solo la nuestra + progreso + exito --------------------------
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
; Salida en la carpeta de release de DaVinciExportador (la que usa
; scripts/packaging/Build-Installer.ps1).
OutputDir=..\..\release
OutputBaseFilename={#MyAppDirectory}-Setup-{#MyAppVersion}
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
ShowLanguageDialog=no
; --- Identidad visual moderna + tema claro/oscuro automatico (IS 6.6+) ---
WizardStyle=modern {#MyAppTheme}
#if MyAppTheme == "dark"
WizardBackColor=#15191C
WizardImageBackColor=#15191C
#else
WizardBackColor=#F7F9FA
WizardImageBackColor=clWhite
#endif
WizardBackColorDynamicDark=#15191C
WizardImageBackColorDynamicDark=#15191C
; --- Instalacion por usuario (sin privilegios de administrador) -------------
; PrivilegesRequiredOverridesAllowed se deja vacio a proposito: abrir el
; dialogo "Seleccion del Modo de Instalacion" anade una pantalla extra.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; --- Comportamiento --------------------------------------------------------
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoDescription={#MyAppName} instalador
VersionInfoProductName={#MyAppName}
VersionInfoCompany=Biglex

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
spanish.FinishedHeadingLabel=Instalación completada
spanish.FinishedLabel={#MyAppName} se instaló correctamente.
spanish.FinishedLabelNoIcons={#MyAppName} se instaló correctamente.
spanish.ClickFinish=Pulsa Finalizar para cerrar el instalador.

[CustomMessages]
spanish.RunApp=Ejecutar {#MyAppName}

[Files]
; Extraído explícitamente por la UI; al principio para evitar descomprimir payload solid.
Source: "{#MyAppIcon}"; Flags: dontcopy
; Artefacto de escritorio empaquetado (PyInstaller, modo onedir) preparado
; por scripts/packaging/Build-Installer.ps1 en packaging\windows\build\dist.
; Sin `ignoreversion`: los binarios internos no llevan version y deben
; reescribirse en cada actualizacion.
Source: "{#MyAppPayload}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
; Acceso directo de escritorio: no anade paginas al asistente.
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"

[Run]
; Lanza la app via el shell del escritorio: heredar el contexto del instalador
; hace que el proceso falle con 0xc00004bc. explorer.exe vive en {win}, no en {sys}.
Filename: "{win}\explorer.exe"; Parameters: """{app}\{#MyAppExe}"""; Description: "{cm:RunApp}"; Flags: nowait postinstall skipifsilent

; Si ya hay eventos en la app, integrar estas llamadas sin borrar sus hooks.
#include "BiglexModernUI.iss"

[Code]
procedure InitializeWizard();
begin
  ModernInitialize;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  ModernPageChanged(CurPageID);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := ModernNextButtonClick(CurPageID);
end;

[Code]
procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  ModernCancelButtonClick(CurPageID, Cancel, Confirm);
end;
