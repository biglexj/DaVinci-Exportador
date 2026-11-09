#!/usr/bin/env bun
import { publishRelease } from "../../Scripts/releases/aurora-publisher.ts";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { relative, resolve, join } from "node:path";

const root = resolve(import.meta.dir, "..");

function readTomlVersion(path: string): string {
    const content = readFileSync(path, "utf-8");
    const m = content.match(/^version\s*=\s*"([^"]+)"/m);
    if (!m) throw new Error("No se pudo leer la versión en " + path);
    return m[1];
}

function sha256(filePath: string): string {
    const buffer = readFileSync(filePath);
    return createHash("sha256").update(buffer).digest("hex");
}

function runCmdSync(cmd: string[], cwd = root): { stdout: string; stderr: string; code: number } {
    const res = Bun.spawnSync(cmd, { cwd, stdout: "pipe", stderr: "pipe" });
    return {
        stdout: res.stdout.toString().trim(),
        stderr: res.stderr.toString().trim(),
        code: res.exitCode ?? 0,
    };
}

const appVersion = readTomlVersion(join(root, "pyproject.toml"));
const appName = "DaVinci Exportador";
const repository = "biglexj/DaVinci-Exportador";

// El stack del proyecto es uv con un único .venv (pyproject.toml + uv.lock).
// Se usa ese entorno cuando existe; si no, se delega en `uv run`, que lo
// prepara; como último recurso, el `python` del sistema.
function findUv(): string | null {
    const fromPath = Bun.which("uv");
    if (fromPath) return fromPath;
    const home = process.env.USERPROFILE;
    if (home) {
        const candidate = join(home, ".local", "bin", "uv.exe");
        if (existsSync(candidate)) return candidate;
    }
    return null;
}

function resolvePythonCmd(): string[] {
    const venvPython = join(root, ".venv", "Scripts", "python.exe");
    if (existsSync(venvPython)) return [venvPython];
    const uv = findUv();
    if (uv) return [uv, "run", "python"];
    return ["python"];
}

const pythonCmd = resolvePythonCmd();

// PowerShell 5.1 es el intérprete con el que se valida el empaquetado Inno
// (Build-Installer.ps1 lo contempla de forma explícita).
const buildInstaller = join(root, "scripts", "packaging", "Build-Installer.ps1");
const powershellCmd = [
    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", buildInstaller,
];

// Verificación de contratos del proyecto: los scripts de implementación no
// deben llevar rutas absolutas al disco local (estándar global de scripts).
// Las plantillas .iss quedan fuera: la plantilla visual compartida contiene
// rutas de ejemplo dentro de mensajes para el usuario.
function listarArchivos(dir: string): string[] {
    if (!existsSync(dir)) return [];
    const salida: string[] = [];
    for (const entrada of readdirSync(dir, { withFileTypes: true })) {
        const completo = join(dir, entrada.name);
        if (entrada.isDirectory()) salida.push(...listarArchivos(completo));
        else salida.push(completo);
    }
    return salida;
}

function rutasAbsolutasEnScripts(): string[] {
    const objetivos = [
        join(root, "scripts"),
        join(root, "packaging", "windows", "launcher"),
    ];
    const archivos = objetivos.flatMap((dir) => listarArchivos(dir));
    if (existsSync(join(root, "main.py"))) archivos.push(join(root, "main.py"));

    const hallazgos: string[] = [];
    for (const archivo of archivos) {
        if (!/\.(ts|ps1|cmd|bat|py)$/i.test(archivo)) continue;
        const lineas = readFileSync(archivo, "utf-8").split(/\r?\n/);
        lineas.forEach((linea, indice) => {
            // Letra de unidad + dos puntos + barra. El limite de palabra
            // evita confundir "https://" con una ruta de disco.
            if (/\b[A-Za-z]:[\\/]/.test(linea)) {
                hallazgos.push(`${relative(root, archivo)}:${indice + 1}: ${linea.trim()}`);
            }
        });
    }
    return hallazgos;
}

// La importación no debe abrir la app ni ejecutar operaciones: solo comprueba
// que motor e interfaz cargan sin efectos secundarios.
const IMPORT_SMOKE = [
    "import sys",
    "sys.path[:0] = ['src', 'src-flet']",
    "import davinci_exportador",
    "import app.app",
    "import features.exportar.exportar_view",
    "import features.empaquetar.empaquetar_view",
    "import shared.components",
    "print('importacion correcta')",
].join("; ");

const help = `DaVinci Exportador: mise <dev|build|check|test|release|publish> [opciones]
  dev      Ejecutar en modo desarrollo (Flet Desktop).
  build    Generar el ejecutable de escritorio (PyInstaller), sin instalador.
  check    Verificar sintaxis, importacion y contratos, sin generar artefactos.
  test     Ejecutar las pruebas unitarias del motor y de la capa de servicio.
  release  Generar instalador oficial Inno Setup en release/.
  publish  [github|all] Publicar en GitHub y sincronizar ficha en Aurora.
  --plan   Mostrar los comandos o el plan sin ejecutar acciones ni escribir.
  --check  Para publish: verificar requisitos locales y remotos sin escribir.

Ejemplos:
  mise dev
  mise dev --plan
  mise build --plan
  mise check --plan
  mise test --plan
  mise release --plan
  mise publish --plan
  mise publish github --plan
  mise publish --check
`;

function assertOpciones(action: string, args: string[], permitidas: string[]): void {
    for (const arg of args) {
        if (arg.startsWith("-") && !permitidas.includes(arg)) {
            throw new Error(`Opción desconocida para '${action}': ${arg}. Opciones admitidas: ${permitidas.join(", ")}.`);
        }
    }
}

async function runPasos(pasos: { titulo: string; cmd: string[] }[], isPlan: boolean): Promise<number> {
    for (const paso of pasos) {
        console.log(`\n==> ${paso.titulo}`);
        console.log(`    ${paso.cmd.join(" ")}`);
        if (isPlan) continue;
        const child = Bun.spawn(paso.cmd, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        const code = (await child.exited) ?? 0;
        if (code !== 0) {
            console.error(`\n❌ Falló: ${paso.titulo} (código ${code})`);
            return code;
        }
    }
    return 0;
}

export async function main(args = Bun.argv.slice(2)): Promise<number> {
    const [action, ...rest] = args;
    if (!action || action === "--help" || rest.includes("--help")) {
        console.log(help);
        return 0;
    }

    if (action === "publish") {
        return publishRelease({
            slug: "davinci-exportador",
            appName: "DaVinci Exportador",
            repository: "biglexj/DaVinci-Exportador",
            version: appVersion,
            projectRoot: root,
            primaryAssetPattern: new RegExp(`^DaVinciExportador.*\\.exe$`, "i"),
            build: async (isPlan) => {
                const psArgs = ["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File","./scripts/packaging/Build-Installer.ps1","-LocalOnly"];
                if (isPlan) return 0;
                const child = Bun.spawn(psArgs, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
                return (await child.exited) ?? 0;
            }
        }, rest);
    }

    assertOpciones(action, rest, ["--plan"]);
    const isPlan = rest.includes("--plan");

    if (action === "dev") {
        const cmd = [...pythonCmd, "main.py"];
        console.log(`dev ${appName}\nDirectorio: ${root}\nComando: ${cmd.join(" ")}`);
        if (isPlan) return 0;
        const child = Bun.spawn(cmd, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        return (await child.exited) ?? 0;
    }

    if (action === "check") {
        const pasos = [
            { titulo: "Verificando sintaxis de Python", cmd: [...pythonCmd, "-m", "compileall", "-q", "src", "src-flet", "main.py", "tests"] },
            { titulo: "Verificando la importación de motor e interfaz", cmd: [...pythonCmd, "-c", IMPORT_SMOKE] },
        ];
        console.log(`check ${appName}\nDirectorio: ${root}`);
        if (isPlan) {
            for (const paso of pasos) console.log(`  ${paso.titulo}: ${paso.cmd.join(" ")}`);
            return 0;
        }
        const codigo = await runPasos(pasos, false);
        if (codigo !== 0) return codigo;

        console.log("\n==> Verificando que los scripts no fijen rutas absolutas al disco local");
        const hallazgos = rutasAbsolutasEnScripts();
        if (hallazgos.length) {
            console.error("❌ Rutas absolutas detectadas en scripts/:");
            for (const hallazgo of hallazgos) console.error(`   ${hallazgo}`);
            return 1;
        }
        console.log("   Sin rutas absolutas en scripts/, launcher ni main.py.");
        console.log("\n✅ check completado");
        return 0;
    }

    if (action === "test") {
        const cmd = [...pythonCmd, "-m", "unittest", "discover", "-s", "tests", "-v"];
        console.log(`test ${appName}\nDirectorio: ${root}\nComando: ${cmd.join(" ")}`);
        if (isPlan) return 0;
        const child = Bun.spawn(cmd, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        return (await child.exited) ?? 0;
    }

    if (action === "build") {
        const pasos = [
            { titulo: "Verificando sintaxis de Python", cmd: [...pythonCmd, "-m", "compileall", "-q", "src", "src-flet", "main.py", "tests"] },
            { titulo: "Generando el ejecutable de escritorio (PyInstaller, sin instalador)", cmd: [...powershellCmd, "-SkipInstaller", "-LocalOnly"] },
        ];
        console.log(`build ${appName}\nDirectorio: ${root}`);
        if (isPlan) {
            for (const paso of pasos) console.log(`  ${paso.titulo}: ${paso.cmd.join(" ")}`);
            return 0;
        }
        return runPasos(pasos, false);
    }

    if (action === "release") {
        const psArgs = ["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File","./scripts/packaging/Build-Installer.ps1","-LocalOnly"];
        console.log(`release ${appName}\nDirectorio: ${root}\nComando: ${psArgs.join(" ")}`);
        if (isPlan) return 0;

        const child = Bun.spawn(psArgs, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        return (await child.exited) ?? 0;
    }

    throw new Error(`Acción desconocida: ${action}. Usa mise dev, mise build, mise check, mise test, mise release o mise publish.`);
}

if (import.meta.main) {
    const args = process.env.MISE_TASK_NAME
        ? [process.env.MISE_TASK_NAME, ...Bun.argv.slice(2)]
        : Bun.argv.slice(2);
    try {
        process.exit(await main(args));
    } catch (err: any) {
        console.error(err?.message ?? err);
        process.exit(1);
    }
}
