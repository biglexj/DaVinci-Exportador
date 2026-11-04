---
trigger: always_on
---

# Instrucciones del proyecto — DaVinci Exportador

## Documentación Core — entrada compartida

Consultar primero [Documentación Core](../../../Docs/README.md) y seleccionar solo los módulos pertinentes. Los estándares compartidos se mantienen allí; este archivo conserva el alcance y los contratos específicos del proyecto.

- [Calidad y entrega proporcionales](../../../Docs/global/quality/quality-baseline.md): build para ajustes visuales pequeños; pruebas pertinentes para elementos, lógica o páginas nuevos y cambios grandes; revisión acotada para documentación.
- [Procesos según alcance](../../../Docs/global/documentation/process-workflow.md): no añadir fases, archivos ni nuevas aprobaciones por rutina a ajustes pequeños ya autorizados.
- [Comandos mediante Mise](../../../Docs/global/architecture/mise-command-standard.md) y [scripts y alias de comandos](../../../Docs/global/architecture/command-scripts-standard.md): Mise es la interfaz de comandos; `release` prepara artefactos y `publish` publica de forma explícita.
- [Base de Python](../../../Docs/stacks/python/python-baseline.md): `uv` con un único `.venv`, motor en `src/` y capa visual en `src-flet/`.
- [Diseño común](../../../Docs/global/design/design_system.md) e [interface writing](../../../Docs/global/design/interface-writing.md): identidad visual y textos de la ventana.
- [Estilo de comunicación](../../../Docs/global/agents/communication-style.md): Scientific Elegant en informes y explicaciones.
- [Base de lanzamientos](../../../Docs/global/releases/release-baseline.md) y [protocolo de lanzamiento](../../../Docs/global/releases/protocolo_lanzamiento_actualizacion.md): versionado, artefactos y publicación.
- [Instaladores](../../../Docs/features/installer/README.md) e [instalación en Windows](../../../Docs/platforms/windows/installer.md): plantilla Inno Setup del ecosistema.
- [Soporte oficial](../../../Docs/features/official-support/official-support-baseline.md): autoría, licencia y enlaces oficiales.
- [Gobernanza de la documentación](../../../Docs/global/documentation/documentation-governance.md), [diagnósticos reutilizables](../../../Docs/troubleshooting/README.md) y [promoción a Core](../../../Docs/global/documentation/core-promotion-workflow.md).

Entrada única de instrucciones: `.agents/rules/base.md`. No se crean `agent.md` ni `AGENTS.md` equivalentes en la raíz.

En estos criterios comunes, aplicar las bases vigentes enlazadas en lugar de copias históricas de este archivo. Respetar la dirección actual de Biglex y los contratos específicos del producto; ante una contradicción, comprobar la implementación vigente y resolverla explícitamente.

## Alcance del producto

Aplicación de escritorio (Flet) para Windows que convierte composiciones Fusion de una bandeja exportada en títulos `.setting` y los reúne en un paquete `.drfx` instalable, sin usar comandos.

- No se instala en Resolve, no modifica proyectos y no sobrescribe destinos. No necesita Resolve abierto.
- El motor (`src/davinci_exportador/`) no depende de Flet: se usa como biblioteca, desde la línea de comandos o desde la app. La interfaz (`src-flet/`) depende del motor, nunca al revés.
- Uso, estructura y alcance completo: [README](../../README.md).

## Contratos técnicos locales

- Preservar originales y destinos: las exportaciones se crean siempre en una carpeta nueva.
- El núcleo es importable sin ejecutar operaciones al importarlo.
- No ejecutar Lua, expresiones ni botones contenidos en los archivos de entrada.
- La lectura de `CompositionBA` y `MpFolder.xml` usa un formato interno de Resolve: rechazar formatos desconocidos y documentar los límites.
- No presentar la inspección de archivos ni la carga de macros como validación de render o de catálogo de Resolve.
- Las exportaciones DRP/DRB no son respaldos completos de medios.
- La exportación nativa de proyectos a DRP sigue sin implementarse y necesita autorización adicional. No crear un DRP renombrando un ZIP de plantillas.
- Solo se convierten composiciones con exactamente un `TextPlus` y un `MediaOut` raíz; no se elige entre varios textos o salidas.
- Los nodos de medios externos del nivel raíz se rechazan por defecto; la opción avanzada los permite sin incrustar medios ni resolver rutas.
- No se instalan fuentes ni se comprueba su disponibilidad; las fuentes declaradas figuran en el manifiesto y en el informe.
- El empaquetador no descarga dependencias ni convierte rutas absolutas en relativas.
- Los archivos se dividen al superar 900 líneas: el motor se separa por responsabilidad (modelo, lectura, conversión, reglas, inventario, empaquetado, controller) y ninguna vista supera ese límite.

## Comandos, rutas y configuración

- Mise es la interfaz de comandos: `mise dev`, `mise build`, `mise check`, `mise test`, `mise release`, `mise publish`.
  - `dev` ejecuta la app de escritorio; `build` genera el ejecutable sin instalador; `check` verifica sintaxis, importación y contratos; `test` ejecuta las pruebas unitarias; `release` genera el instalador en `release/`; `publish` es explícito y exige autorización.
  - `--plan` no ejecuta ni escribe; `--check` solo verifica. Ninguno publica ni instala.
- Entorno único `.venv` gestionado con `uv` (`pyproject.toml`, `uv.lock`).
- Empaquetado: ejecutable en `packaging/windows/launcher/`, instalador Inno Setup en `packaging/windows/`, script de compilación en `scripts/packaging/Build-Installer.ps1`.
- Icono oficial: `assets/branding/icons/`. Ejemplo de reglas de atribución: `ejemplos/snap-captions.json`.
- Temporales y exportaciones locales en `scratch/` o `exports/` (ignorados por git).
- Pruebas en `tests/` con `unittest`; no requieren Resolve.

## Diagnóstico

- El empaquetado rechaza binarios más viejos que el código fuente: consultar la guía de Core [instalador con binario viejo](../../../Docs/troubleshooting/tools/inno-stale-binary-packaging.md) antes de forzar con `-ForceStale`.
