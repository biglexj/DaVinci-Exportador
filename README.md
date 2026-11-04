# DaVinci Exportador

Mini app de escritorio para Windows que convierte composiciones Fusion de una
bandeja exportada en títulos `.setting` y los reúne en un paquete `.drfx`
instalable, sin usar comandos.

La app no duplica la lógica: el motor vive en `src/davinci_exportador`, se
puede usar como biblioteca, desde la línea de comandos o desde la app de
escritorio.

- Versión de la app: **0.2.0**. Python **3.10 o posterior**.
- No necesita Resolve abierto para convertir o empaquetar archivos ya exportados.
- No instala nada en Resolve, no modifica proyectos y no sobrescribe destinos.

## Operación con Mise (Estándar Ecosistema)

DaVinci Exportador implementa la interfaz universal de tareas mediante Mise:

| Tarea | Propósito |
|---|---|
| `mise dev` | Ejecutar en modo desarrollo (Flet Desktop). |
| `mise build` | Generar el ejecutable de escritorio (PyInstaller) sin instalador. |
| `mise check` | Verificar sintaxis, importación de motor e interfaz y contratos de los scripts, sin generar artefactos. |
| `mise test` | Ejecutar las pruebas unitarias del motor y de la capa de servicio. |
| `mise release` | Generar instalador oficial Inno Setup en `release/` sin publicar. |
| `mise publish` | Publicar en GitHub Releases y sincronizar ficha en Aurora (`--plan` y `--check` sin escritura). |

Opciones de inspección y comprobación:
- `--plan`: Muestra el comando y las operaciones planificadas sin ejecutar procesos ni modificar el sistema (`mise dev --plan`, `mise build --plan`, `mise check --plan`, `mise test --plan`, `mise release --plan`, `mise publish --plan`).
- `--check`: (para `publish`) Verifica el estado del repositorio, tags, notas y la presencia e integridad del instalador en `release/` sin publicar nada (`mise publish --check`).
- Canal explícito `github`: `mise publish github` (omite la sincronización con la web de Aurora).

`release` prepara artefactos y no publica; `publish` es la única tarea con efecto
remoto y exige autorización explícita. Ninguna tarea publica ni instala en
modo `--plan` o `--check`.

## Ejecutar la app (Método Directo)

El proyecto usa `uv` con un único entorno `.venv`. `mise dev` es la entrada
canónica; estos comandos son alias equivalentes:

```powershell
uv sync
uv run python main.py
```

La primera ejecución prepara el cliente de escritorio de Flet; a partir de ahí
se abre la ventana «DaVinci Exportador».

Sin `uv`, con un Python instalado y Flet disponible:

```powershell
python main.py
```

## Qué ofrece

La ventana tiene dos operaciones, elegibles en la parte superior.

### Exportar títulos

1. **Elegir origen** — una bandeja `.drb`, un proyecto `.drp` ya exportado o un
   archivo `.comp` o `.setting`.
2. **Seleccionar contenido** — las carpetas y composiciones del archivo, con
   una casilla por título. Las que no se pueden exportar aparecen desactivadas
   con el motivo (falta un `TextPlus` o un `MediaOut` en el nivel raíz, o el
   archivo usa un formato interno que esta versión no reconoce). Se pueden
   marcar todas las compatibles de una vez.
3. **Revisar destino** — creador, colección, nombre base y crédito opcional,
   con una vista previa del nombre y la carpeta final de cada título. Debajo,
   en bloques plegables, la atribución por carpeta y las opciones avanzadas
   (quitar prefijo, guiones, mayúsculas y medios externos).
4. **Exportar** — el destino es siempre una **carpeta nueva**. Al terminar se
   puede crear además el paquete `.drfx`.

El creador general viene puesto como **Biglex J**; se cambia en el mismo
campo. La atribución del creador se mantiene separada de la autoría de una
adaptación: los valores por carpeta se configuran aparte de los generales y el
motor no adivina creadores.

### Empaquetar plantillas

1. **Elegir carpeta** — la que contiene `Edit/Titles`, `Edit/Effects`,
   `Edit/Generators` o `Edit/Transitions`.
2. **Comprobar estructura** — sin escribir nada, indica cuántos títulos,
   cuántos recursos y qué categorías hay.
3. **Elegir destino** — el archivo `.drfx`, que no puede existir todavía.
4. **Crear paquete** — se genera y se comprueba su integridad.

En ambos casos el resultado indica dónde están los archivos, permite abrir la
carpeta y consultar el informe.

## Línea de comandos

El motor sigue disponible sin interfaz. `main.py` delega en la línea de
comandos cuando recibe argumentos:

```powershell
uv run python main.py --help
uv run python main.py listar 'D:\Exportaciones\Mis títulos.drb'
uv run python main.py exportar 'D:\Exportaciones\Mis títulos.drb' --salida '.\exports\mis-titulos'
uv run python main.py empaquetar '.\exports\mis-titulos\Templates' --salida '.\exports\mis-titulos.drfx'
```

También funciona el módulo del motor directamente:

```powershell
uv run python -m davinci_exportador --help
```

`listar` añade a cada composición si es compatible y el motivo si no lo es; los
problemas de lectura de una entrada se avisan por `stderr` sin ocultar el resto
del archivo.

La salida de `exportar` es una carpeta **nueva**:

```text
mis-titulos/
  Templates/Edit/Titles/<creador>/<colección>/<carpeta de origen>/*.setting
  manifest.json
  titulos.csv
```

El JSON de reglas permite configurar `creator`, `collection`, `credit`,
`prefix`, `strip_prefix`, `replace_hyphens`, `title_case` y `subfolder`. Las
reglas se aplican por nombre exacto de carpeta. `subfolder: null` elimina ese
nivel; un texto lo sustituye. Sin `subfolder`, se conserva la carpeta de origen
para distinguir versiones. Si dos títulos producirían el mismo destino, se
cancela toda la exportación antes de publicar archivos.

## Ejemplo: Orson Lord y adaptaciones de Biglex J

```powershell
uv run python main.py exportar 'D:\Exportaciones\Snap Captions.drb' --salida '.\exports\subtitulos' --carpeta '1.5' --carpeta '1.6' --carpeta 'V2' --carpeta 'biglexj' --config '.\ejemplos\snap-captions.json'
uv run python main.py empaquetar '.\exports\subtitulos\Templates' --salida '.\exports\subtitulos.drfx'
```

El ejemplo atribuye los originales a **Orson Lord** y termina tus adaptaciones
en **OL**. El script no adivina creadores.

## Estructura

La raíz no tiene lógica: solo `main.py`, que prepara las rutas y decide si se
abre la app o la línea de comandos.

```text
main.py                    Punto de entrada único: app de escritorio o CLI
mise.toml                  Tareas canónicas del proyecto (dev, build, check, test, release, publish)
scripts/mise-task.ts       Despachador único de las tareas de Mise
src/davinci_exportador/    Motor (sin dependencias, sin Flet)
  modelo.py                Composicion, Lectura, Node
  fusion.py                Lectura de las tablas Fusion comprimidas
  lectura.py               Lectura de DRB, DRP, .comp y .setting
  conversion.py            Conversion a .setting y publicacion de la carpeta
  nombres.py               Saneado de nombres y calculo del destino
  reglas.py                Opciones de atribucion y previsualizacion
  inventario.py            Que se puede exportar y por que
  empaquetado.py           Empaquetado DRFX
  controller.py            Operaciones de alto nivel que consume la interfaz
  cli.py                   Linea de comandos
src-flet/                  Interfaz de escritorio (Flet)
  app/                     Carcasa de la ventana y tema
  features/exportar/       Vista de exportacion de titulos
  features/empaquetar/     Vista de empaquetado
  shared/                  Piezas visuales compartidas
assets/branding/icons/     Icono oficial (PNG transparente e ICO de Windows)
packaging/windows/         PyInstaller (.spec), lanzador e instalador Inno
scripts/packaging/         Compilacion del ejecutable y del instalador
tests/                     Pruebas del motor y de la capa de servicio
```

El icono oficial se aplica al ejecutable, al instalador y a los accesos
directos. En la barra de título de la ventana sigue el icono del cliente de
escritorio de Flet 1.x, que lo fuerza y no acepta cambios desde Python.

El motor no depende de Flet y la interfaz no duplica su lógica: la dependencia
va siempre de `src-flet` hacia `src`.

## Compilar el instalador

Mise es la entrada de comandos:

```powershell
mise build    # ejecutable de escritorio, sin instalador
mise release  # instalador Inno Setup en release\
```

Ambos terminan en el mismo script, `scripts/packaging/Build-Installer.ps1`, que
regenera `packaging\windows\version.iss` con la versión de `pyproject.toml`,
compila el ejecutable de escritorio con PyInstaller (incluye el cliente de
Flet y el icono oficial) y, en el caso de `release`, genera el instalador Inno
Setup en `release\`. Con `-SkipDesktopBuild` reutiliza el ejecutable ya
compilado. El script solo produce artefactos locales: la publicación remota
vive en `mise publish`.

Desde la raíz, el mismo punto de entrada orquesta también la compilación:

```powershell
uv run python main.py build
```

Equivale a:

```powershell
pwsh -File scripts\packaging\Build-Installer.ps1 -LocalOnly
```

## Alcance y límites

- Lee DRB, DRP ya exportados, `.comp` de texto y `.setting` compatibles. En los
  contenedores busca `MpFolder.xml` y `CompositionBA`, observados en Resolve
  21.1; esos formatos internos pueden cambiar.
- La lectura de **DRP** como entrada es experimental. **La app todavía no
  exporta proyectos a DRP** ni construye proyectos nuevos. El formato de
  contenedor se comparte con DRB, pero esta entrega se ha probado con la
  bandeja DRB real, no con todos los tipos de proyecto DRP.
- Convierte composiciones con exactamente **un TextPlus y un MediaOut raíz**. No
  intenta elegir entre varios textos o salidas; la app explica cuáles quedan
  fuera y por qué.
- Publica los controles básicos de texto y los controles personalizados del
  TextPlus; conserva los nodos interiores y sus animaciones. No normaliza
  tiempos, resolución ni estilos.
- Detecta nodos de medios externos del nivel raíz y los rechaza por defecto. La
  opción avanzada «Permitir títulos que usan medios externos» permite continuar
  conservando las referencias, **sin incrustar medios ni resolver rutas**. Esa
  detección no sustituye una auditoría completa de dependencias dentro de
  grupos, scripts o expresiones.
- No instala fuentes ni comprueba su disponibilidad; las fuentes declaradas
  figuran en el manifiesto y en el informe. No ejecuta el código Lua incluido
  en plantillas.
- El empaquetador incluye los recursos que ya estén en la carpeta seleccionada.
  No descarga dependencias ni convierte rutas absolutas en relativas.
- No instala paquetes, no modifica Reactor, no reinicia Resolve y no sobrescribe
  fuentes o destinos existentes.
- La comprobación de estructura y hashes no prueba render, temporización,
  botones del Inspector ni aparición en el catálogo. Esas pruebas se hacen en
  Resolve sobre una copia.

Las exportaciones DRP/DRB no deben confundirse con respaldos completos de medios.

## Pruebas

```powershell
mise test
```

Equivale a:

```powershell
uv run python -m unittest discover -s tests -v
```

Las pruebas cubren conservación de nodos y expresiones, nombres duplicados,
rechazo de dependencias externas, protección de destinos, lectura con problemas
por entrada, selección de títulos, reglas de atribución por carpeta y creación
del paquete. No requieren Resolve ni incluyen plantillas privadas en el
repositorio.

Comprobación local del 23 de octubre de 2026: 27 pruebas correctas; la app se
abrió y se recorrió el flujo completo (origen, selección, destino, exportación
y empaquetado) sobre una bandeja de prueba, con captura de pantalla de cada
paso. Esa comprobación no instaló los resultados ni probó su render en
Resolve.

## Licencia

Distribuido bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

