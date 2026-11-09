# 🎬 Release Notes — DaVinci Exportador

> [!IMPORTANT]
> **Protocolo de Verificación de Versión en GitHub ("Lanzar actualización") [CRÍTICO]:**
> - Al recibir la orden de *"Lanzar actualización"*, es **OBLIGATORIO Y DE LEY** consultar primero la última versión publicada en GitHub / remoto (`gh release list` o `git ls-remote --tags`).
> - Si la versión local ya fue subida (así haya sido lanzada hace minutos), NUNCA se debe sobrescribir ni re-etiquetar. Se DEBE incrementar obligatoriamente a la siguiente versión de parche (e.g. `0.2.0` → `0.2.1`).
>
> **Sanitización de Notas (CRÍTICO):**
> - Los mensajes de las notas de lanzamiento DEBEN estar limpios de rutas de archivos del sistema local (ej. `d:\Proyectos\...`), nombres de variables internas, fragmentos de prompts o logs técnicos de depuración. Deben redactarse con lenguaje limpio, profesional y enfocado al usuario final.
>
> **Estándar SemVer Flexible (Core-Docs v1.7.0):**
> - Se utiliza SemVer estándar (`MAJOR.MINOR.PATCH`) sin límites artificiales por dígito (segmentos mayores a 9 como `0.2.12` son 100% válidos).
> - Se incrementa `PATCH`, `MINOR` o `MAJOR` según el alcance real del cambio y compatibilidad, sin saltos forzados de versión basados únicamente en alcanzar un dígito 9.
> - **Extensión proporcional en Release Notes:** La cantidad de párrafos depende del alcance: 1 para un hito pequeño, 2 cuando hay dos cambios relevantes, 3 como extensión habitual, 4 para hitos relativamente grandes y hasta 5 para lanzamientos de gran alcance. Cada párrafo debe concentrarse en un cambio principal y evitar descripciones excesivamente largas o listas detalladas de archivos.

Registro histórico de cambios y versiones de **DaVinci Exportador**.

---

## [0.2.0] - 2026-11-09 — “Template Packager & DRFX Hub”

### Resumen
Lanzamiento oficial de **DaVinci Exportador v0.2.0**, consolidado como **DaVinci Template Packager (DRFX Hub)**. Esta entrega redefine el propósito de la herramienta para enfocarla en lo que verdaderamente aporta valor a los editores de video: un taller visual robusto para inspeccionar, validar, organizar y empaquetar colecciones de plantillas Fusion en paquetes oficiales `.drfx` listos para instalarse en **DaVinci Resolve 21**, manteniendo un historial de paquetes generados localmente y un motor modular operable tanto desde la interfaz de escritorio en **Flet** como desde la terminal.

### Detalles
- **Pivote a Template Packager & DRFX Hub**: Reorientación integral de la aplicación hacia la inspección y empaquetado de plantillas ya diseñadas en Fusion. Se descarta la conversión rígida y monolítica de composiciones crudas de bandeja (.drb), dando paso a un flujo natural y fiable centrado en las carpetas oficiales de plantillas (`Edit/Titles`, `Edit/Effects`, `Edit/Generators`, `Edit/Transitions`).
- **Inspección Visual del Catálogo y Recursos**: Reconocimiento automático de categorías de Resolve, conteo de recursos auxiliares (.png, .jpg, .lut) y un catálogo interactivo desplegable (*ExpansionTile*) que expone cada archivo `.setting` detectado con su subcarpeta y tamaño en disco antes de compilar.
- **Metadatos de Autoría y Versionado**: Soporte para configurar el autor de la colección (`Biglex J`) y la versión del paquete (`1.0.0`), permitiendo documentar la procedencia de cada distribución de títulos y reflejarla en los informes de empaquetado.
- **Historial Persistente de Paquetes Creados**: Nueva sección de historial accesible desde la barra superior que guarda registro de los paquetes `.drfx` compilados en el equipo (con fecha, recuento de plantillas, ruta y hash SHA-256), incluyendo botón para abrir la carpeta directamente en el Explorador de Windows.
- **Garantía Estricta de Destinos y No Sobrescritura**: La aplicación comprueba que el paquete de salida no exista previamente para evitar pérdidas accidentales de trabajo, verificando la integridad del contenedor ZIP antes de confirmarlo al usuario.
- **Instalador de Windows Modernizado (Inno Setup)**: Compilación del instalador oficial `.exe` con la plantilla "Biglex Modern 2.0", con instalación por usuario sin elevación obligatoria de privilegios y soporte automático de tema claro/oscuro de Windows 11/10.
