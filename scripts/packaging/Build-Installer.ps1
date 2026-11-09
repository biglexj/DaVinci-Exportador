<#
.SYNOPSIS
    Compila el instalador de Windows de DaVinci Exportador con la plantilla
    "Biglex Modern 2.0" (Inno Setup 6.7+).

.DESCRIPTION
    El script hace cuatro cosas, en este orden:

    1. Regenera `packaging\windows\version.iss` con la version real leida de
       `pyproject.toml`.
    2. Prepara el artefacto de escritorio: compila el bundle onedir de
       PyInstaller (`packaging\windows\launcher\DaVinciExportador.spec`), que
       incluye el cliente de escritorio de Flet para que la app funcione sin
       descarga en la primera ejecucion.
    3. Compila `packaging\windows\setup.iss` con ISCC y deja el instalador en
       la carpeta de release (`release\`).

    Antes de invocar ISCC.exe el builder sincroniza la plantilla visual
    compartida y pasa el validador de invariantes de empaquetado
    (`Scripts\tools\inno\Check-Packaging.ps1`), que aborta la compilacion si el
    arranque post-instalacion vuelve a lanzar la app directamente desde el
    instalador (fallo 0xc00004bc), si el nombre de salida lleva el sufijo
    obsoleto `_x64` o si la plantilla visual diverge de la compartida.

    Con `-SkipInstaller` se detiene tras el paso 2 y deja el ejecutable de
    escritorio listo, sin generar instalador: es la variante de `build`.

    No modifica codigo de produccion: solo `packaging\windows\` y `release\`.

.PARAMETER SkipDesktopBuild
    No recompila el ejecutable de escritorio; reutiliza el bundle existente en
    `packaging\windows\build\dist\DaVinciExportador`.

.PARAMETER SkipInstaller
    No compila el instalador Inno Setup: deja preparado solo el ejecutable de
    escritorio en `packaging\windows\build\dist\DaVinciExportador`. Es la
    variante que usa la tarea `build` de Mise.

.PARAMETER LocalOnly
    Contencion explicita del estandar global de scripts: la operacion se
    limita a artefactos locales. Este script no tiene ninguna ruta de
    publicacion remota, asi que el flag documenta esa intencion y no cambia
    el resultado. La publicacion en remoto solo existe en `mise publish`.

.PARAMETER OutputDir
    Carpeta de salida del instalador. Por defecto, `release\` en la raiz del repo.

.PARAMETER FletVersion
    Version de `flet[desktop]` con la que se compila. Por defecto, la fijada en
    `pyproject.toml`.

.EXAMPLE
    pwsh -File scripts\packaging\Build-Installer.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipDesktopBuild,
    [switch]$SkipInstaller,
    [switch]$LocalOnly,
    [string]$OutputDir,
    # Empaqueta aunque el artefacto sea mas viejo que el codigo fuente. Solo
    # para depurar: publicar asi reintroduce el build obsoleto.
    [switch]$ForceStale,
    # Ruta al compilador de Inno Setup. Si se deja vacia se localiza relativa
    # al repositorio y, en su defecto, en el PATH (ver Resolve-Iscc).
    [string]$Compiler = '',
    [string]$FletVersion = ''
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$packaging = Join-Path $root 'packaging\windows'
$build = Join-Path $packaging 'build'
$buildVenv = Join-Path $build 'venv'
$cache = Join-Path $build 'cache'
$artifact = Join-Path $build 'dist\DaVinciExportador'
$clientZip = Join-Path $cache 'flet-windows.zip'
$spec = Join-Path $packaging 'launcher\DaVinciExportador.spec'
$launcher = Join-Path $packaging 'launcher\DaVinciExportador.py'
$iss = Join-Path $packaging 'setup.iss'
$versionIss = Join-Path $packaging 'version.iss'
$identityIss = Join-Path $packaging 'identity.iss'
$uiIss = Join-Path $packaging 'BiglexModernUI.iss'
$iconIss = Join-Path $packaging 'DaVinciExportador.ico'
$iconSource = Join-Path $root 'assets\branding\icons\icon-windows.ico'

if (-not $OutputDir) {
    # Coincide con OutputDir=..\..\release de packaging\windows\setup.iss:
    # el instalador se publica en release\, no en dist\.
    $OutputDir = Join-Path $root 'release'
}

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

# --- Puerta de calidad de empaquetado (validador compartido) -----------------
# La plantilla visual y el arranque post-instalacion son fuente unica del
# workspace. Un [Run] editado a mano que lance la app directamente desde el
# instalador hace que el proceso herede su contexto y muera con 0xc00004bc
# (STATUS_REDIRECTION_TRUST_FAILURE), asi que el validador compartido aborta
# la compilacion antes de invocar ISCC.exe.
function Resolve-SharedInno {
    $dir = $PSScriptRoot
    for ($i = 0; $i -lt 8; $i++) {
        $candidate = Join-Path $dir 'Scripts\tools\inno'
        if (Test-Path -LiteralPath $candidate) { return $candidate }
        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}

function Sync-SharedTemplate {
    param([string]$SharedDir, [string]$PackagingDir)
    if (-not $SharedDir) { return }
    $src = Join-Path $SharedDir 'BiglexModernUI.iss'
    $dst = Join-Path $PackagingDir 'BiglexModernUI.iss'
    if ((Test-Path -LiteralPath $src) -and (Test-Path -LiteralPath $PackagingDir)) {
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host '    plantilla visual sincronizada con la copia compartida del workspace.' -ForegroundColor Gray
    }
}

function Assert-PackagingInvariants {
    param([string]$SharedDir, [string[]]$SetupFiles)
    if (-not $SharedDir) {
        Write-Host 'AVISO: no se encontro la carpeta compartida Scripts\tools\inno.' -ForegroundColor Yellow
        Write-Host '       Se omite la validacion de invariantes de empaquetado.' -ForegroundColor Yellow
        return
    }
    $checker = Join-Path $SharedDir 'Check-Packaging.ps1'
    if (-not (Test-Path -LiteralPath $checker)) {
        Write-Host "AVISO: no se encontro $checker. Se omite la validacion." -ForegroundColor Yellow
        return
    }
    # Get-Command puede devolver varias rutas (alias de Store y MSIX): se toma
    # la primera que exista de verdad.
    $shellExe = $null
    foreach ($name in @('pwsh', 'powershell')) {
        foreach ($candidate in @(Get-Command $name -CommandType Application -ErrorAction SilentlyContinue)) {
            if ($candidate.Source -and (Test-Path -LiteralPath $candidate.Source)) {
                $shellExe = $candidate.Source
                break
            }
        }
        if ($shellExe) { break }
    }
    if (-not $shellExe) {
        Write-Host 'AVISO: no se encontro pwsh ni powershell: se omite la validacion.' -ForegroundColor Yellow
        return
    }
    foreach ($setup in $SetupFiles) {
        & $shellExe -NoProfile -ExecutionPolicy Bypass -File $checker -SetupIss $setup
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: las invariantes de empaquetado fallan para $setup." -ForegroundColor Red
            Write-Host '       No se compila el instalador. Corrige lo anterior.' -ForegroundColor Red
            exit 1
        }
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][AllowEmptyString()][string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    Push-Location $WorkingDirectory
    try {
        & $Executable @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "El comando '$Executable' termino con codigo de error $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

# --- Candado anti-build-obsoleto -------------------------------------------
# Si el bundle de PyInstaller es mas viejo que el codigo fuente, el instalador
# queda "recien compilado" pero lleva dentro una app vieja.
function Get-NewestWriteTime {
    param([string[]]$Paths)
    $best = $null
    $bestPath = $null
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $item = if (Test-Path -LiteralPath $path -PathType Container) {
            Get-ChildItem -LiteralPath $path -Recurse -File -Force -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1
        }
        else {
            Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
        if ($item -and (-not $best -or $item.LastWriteTime -gt $best)) {
            $best = $item.LastWriteTime
            $bestPath = $item.FullName
        }
    }
    return [pscustomobject]@{ Time = $best; Path = $bestPath }
}

function Assert-BuildFresh {
    param([string]$Artifact, [switch]$Force)
    if (-not (Test-Path -LiteralPath $Artifact)) {
        throw "No existe el artefacto de escritorio esperado: $Artifact"
    }
    $exeItem = Get-Item -LiteralPath $Artifact
    $newest = Get-NewestWriteTime -Paths @(
        (Join-Path $root 'src'),
        (Join-Path $root 'src-flet'),
        (Join-Path $root 'assets'),
        (Join-Path $root 'packaging\windows\launcher'),
        (Join-Path $root 'pyproject.toml')
    )
    if (-not $newest.Time) { return }
    if ($exeItem.LastWriteTime -ge $newest.Time) {
        Write-Step "Artefacto al dia: $($exeItem.LastWriteTime.ToString('dd/MM HH:mm:ss'))"
        return
    }
    $rel = if ($newest.Path) { $newest.Path.Substring($root.Length).TrimStart('\') } else { '(desconocido)' }
    if ($Force) {
        Write-Host "AVISO: se empaqueta un build OBSOLETO por -ForceStale." -ForegroundColor Yellow
        Write-Host "       artefacto $($exeItem.LastWriteTime.ToString('dd/MM HH:mm:ss')) < fuente $($newest.Time.ToString('dd/MM HH:mm:ss')) $rel" -ForegroundColor Yellow
        return
    }
    throw ("El artefacto de escritorio es MAS VIEJO que el codigo fuente:`n" +
           "  artefacto : $($exeItem.LastWriteTime.ToString('dd/MM HH:mm:ss'))  $Artifact`n" +
           "  fuente    : $($newest.Time.ToString('dd/MM HH:mm:ss'))  $rel`n" +
           "Vuelve a compilar el escritorio (sin -SkipDesktopBuild), o usa -ForceStale para depurar.")
}

# Localiza ISCC.exe sin rutas absolutas: primero la copia del workspace,
# subiendo desde este script; despues el PATH del sistema.
function Resolve-Iscc {
    $dir = $PSScriptRoot
    for ($i = 0; $i -lt 8; $i++) {
        $candidate = Join-Path $dir 'Scripts\tools\InnoSetup\ISCC.exe'
        if (Test-Path -LiteralPath $candidate) { return $candidate }
        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) { break }
        $dir = $parent
    }
    $onPath = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    return $null
}

function Resolve-Uv {
    $onPath = Get-Command 'uv' -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $local = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path -LiteralPath $local) { return $local }
    return $null
}

# --- 1. Version real ------------------------------------------------------
Write-Step 'Leyendo la version de pyproject.toml'
$pyproject = Get-Content -LiteralPath (Join-Path $root 'pyproject.toml') -Raw -Encoding UTF8
$versionMatch = [regex]::Match($pyproject, '(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"')
if (-not $versionMatch.Success) {
    throw 'No se pudo leer la version en pyproject.toml.'
}
$version = $versionMatch.Groups[1].Value
Write-Host "    version: $version"

if (-not $FletVersion) {
    $fletMatch = [regex]::Match($pyproject, 'flet\[desktop\][=><~]*([\d.]+)')
    if ($fletMatch.Success) { $FletVersion = $fletMatch.Groups[1].Value }
}
if (-not $FletVersion) {
    throw 'No se pudo determinar la version de flet[desktop]. Usa -FletVersion.'
}
Write-Host "    flet[desktop]: $FletVersion"

$versionIssContent = @"
; ---------------------------------------------------------------------------
; version.iss - generada por scripts/packaging/Build-Installer.ps1.
; No editar a mano: el build lo reescribe con la version real de pyproject.toml.
;   #define MyAppVersion "$version"
; ---------------------------------------------------------------------------
#define MyAppVersion "$version"
"@
# Inno Setup necesita BOM para leer acentos en un .iss. Se escribe con
# [System.IO.File]::WriteAllText y no con Set-Content -Encoding utf8BOM porque
# ese nombre de codificacion solo existe en PowerShell 7: invocado con
# `powershell` (Windows PowerShell 5.1) fallaba al enlazar el parametro.
$utf8Bom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($versionIss, $versionIssContent, $utf8Bom)
Write-Host "    escrito: $versionIss"

# --- 2. Artefacto de escritorio -------------------------------------------
if (-not $SkipDesktopBuild) {
    Write-Step 'Preparando el entorno de compilacion del ejecutable de escritorio'
    $uv = Resolve-Uv
    if (-not $uv) {
        throw "No se encontro 'uv' (necesario para crear el entorno de compilacion). Buscalo en PATH o en $env:USERPROFILE\.local\bin\uv.exe"
    }

    $buildPython = Join-Path $buildVenv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $buildPython)) {
        Write-Host '    creando el entorno de compilacion...'
        Invoke-Checked $uv @('venv', '--python', '3.13', $buildVenv)
    }
    Write-Host '    instalando flet[desktop] y pyinstaller...'
    Invoke-Checked $uv @('pip', 'install', '--python', $buildPython, "flet[desktop]==$FletVersion", 'pyinstaller>=6.10')

    Write-Step 'Preparando el cliente de escritorio de Flet'
    $clientVersion = & $buildPython -c "import flet_desktop.version as v; print(v.version)"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer la version de flet_desktop.' }
    $clientVersion = $clientVersion.Trim()
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    if (-not (Test-Path -LiteralPath $clientZip)) {
        $clientUrl = "https://github.com/flet-dev/flet/releases/download/v$clientVersion/flet-windows.zip"
        Write-Host "    descargando $clientUrl"
        Invoke-WebRequest -Uri $clientUrl -OutFile $clientZip -UseBasicParsing
    } else {
        Write-Host "    en cache: $clientZip"
    }

    Write-Step 'Compilando el ejecutable de escritorio (PyInstaller, onedir)'
    # El directorio de trabajo no es la raiz del repo: la carpeta 'packaging'
    # del repo no debe ensombrecer el modulo 'packaging' de Python.
    Invoke-Checked (Join-Path $buildVenv 'Scripts\pyinstaller.exe') @(
        '--noconfirm', '--clean',
        '--distpath', (Join-Path $build 'dist'),
        '--workpath', (Join-Path $build 'work'),
        $spec
    ) $build
} else {
    Write-Step 'Reutilizando el ejecutable de escritorio existente'
}

Assert-BuildFresh -Artifact (Join-Path $artifact 'DaVinciExportador.exe') -Force:$ForceStale

Write-Step 'Sincronizando el icono oficial con la carpeta de empaquetado'
Copy-Item -LiteralPath $iconSource -Destination $iconIss -Force

if ($SkipInstaller) {
    Write-Host ''
    Write-Host 'Ejecutable de escritorio listo (sin instalador):' -ForegroundColor Green
    Write-Host "    $(Join-Path $artifact 'DaVinciExportador.exe')"
    Write-Host ''
    Write-Host 'Para generar el instalador usa la tarea release (mise release).' -ForegroundColor Gray
    exit 0
}

# --- 3. Compilacion del instalador ----------------------------------------
Write-Step 'Compilando el instalador con Inno Setup'
if (-not $Compiler) { $Compiler = Resolve-Iscc }
if (-not $Compiler) {
    throw "No se localizo ISCC.exe en Scripts\tools\InnoSetup ni en el PATH."
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$sharedInno = Resolve-SharedInno
Sync-SharedTemplate -SharedDir $sharedInno -PackagingDir $packaging
Assert-PackagingInvariants -SharedDir $sharedInno -SetupFiles @($iss)
Invoke-Checked $Compiler @($iss, "/O$OutputDir")

$installer = Join-Path $OutputDir "DaVinciExportador-Setup-$version.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "El instalador no se genero en la ruta esperada: $installer"
}

# SHA-256 con la API de .NET en lugar de Get-FileHash: ese cmdlet no esta
# disponible en el modulo Microsoft.PowerShell.Utility cuando `powershell` se
# invoca con -NoProfile, que es como lo llama el pipeline de release.
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$stream = $null
try {
    $stream = [System.IO.File]::OpenRead($installer)
    $hash = ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
}
finally {
    if ($stream) { $stream.Dispose() }
    $sha256.Dispose()
}
Write-Host ''
Write-Host 'Instalador generado:' -ForegroundColor Green
Write-Host "    $installer"
Write-Host "    sha256: $hash"
Write-Host ("    tamano: {0:N1} MB" -f ((Get-Item -LiteralPath $installer).Length / 1MB))

# Sincronizar copia en '12. Releases' (carpeta hermana del proyecto dentro
# del workspace). Se resuelve de forma relativa a la raiz del repositorio:
# ningun script fija rutas absolutas al disco local.
$releasesGlobalDir = Join-Path (Split-Path -Parent $root) '12. Releases'
if (Test-Path -LiteralPath $releasesGlobalDir) {
    $installerLeaf = Split-Path $installer -Leaf
    Get-ChildItem -LiteralPath $releasesGlobalDir -Filter "DaVinciExportador-Setup-*.exe" -File |
        Where-Object { $_.Name -ne $installerLeaf } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
    Copy-Item -LiteralPath $installer -Destination (Join-Path $releasesGlobalDir $installerLeaf) -Force
    Write-Host "==> Copia sincronizada en 12. Releases\$installerLeaf" -ForegroundColor Green
}

exit 0
