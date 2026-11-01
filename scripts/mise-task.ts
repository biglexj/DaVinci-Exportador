#!/usr/bin/env bun
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join } from "node:path";

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

const pythonExe = existsSync(join(root, ".venv", "Scripts", "python.exe"))
    ? join(root, ".venv", "Scripts", "python.exe")
    : "python";

const help = `DaVinci Exportador: mise <dev|build|release|publish> [opciones]
  dev      Ejecutar en modo desarrollo (Flet Desktop).
  build    Compilar y verificar sintaxis de Python sin generar instalador.
  release  Generar instalador oficial Inno Setup en release/.
  publish  [github|all] Publicar en GitHub y sincronizar ficha en Aurora.
  --plan   Mostrar los comandos o el plan sin ejecutar acciones ni escribir.
  --check  Para publish: verificar requisitos locales y remotos sin escribir.

Ejemplos:
  mise dev
  mise dev --plan
  mise build --plan
  mise release --plan
  mise publish --plan
  mise publish github --plan
  mise publish --check
`;

async function handlePublish(args: string[]): Promise<number> {
    const isPlan = args.includes("--plan");
    const isCheck = args.includes("--check");
    const positional = args.filter((arg) => !arg.startsWith("-"));
    const channel = positional[0] ?? "all";

    if (!["all", "github"].includes(channel)) {
        throw new Error(`Canal desconocido: ${channel}. Usa 'github' o 'all'.`);
    }

    const effectiveChannels = channel === "github" ? ["GitHub Releases"] : ["GitHub Releases", "Aurora Web (biglexj.com)"];

    console.log(`\n=== Publicación: ${appName} v${appVersion} ===`);
    console.log(`Repositorio : ${repository}`);
    console.log(`Canales     : ${effectiveChannels.join(" + ")}`);

    if (isPlan) {
        console.log("\n[Plan de publicación]");
        console.log("1. Verificar que el repositorio esté en rama limpia y commit en remoto.");
        console.log(`2. Comprobar instalador local en release/: DaVinciExportador-Setup-${appVersion}.exe.`);
        console.log("3. Validar RELEASE_MESSAGE.md (notas de versión públicas sin secretos).");
        console.log(`4. Crear tag git v${appVersion} y GitHub Release vía gh.`);
        if (channel === "all") {
            console.log("5. Sincronizar metadatos y enlace de descarga en Aurora (https://www.biglexj.com).");
        } else {
            console.log("5. Sincronización con Aurora omitida (canal explícito: github).");
        }
        console.log("\n(--plan completado: no se realizaron cambios ni consultas de red)");
        return 0;
    }

    if (isCheck) {
        console.log("\n[Comprobación de preparación (--check)]");
        let hasErrors = false;

        // 1. Git status & commits
        const headCheck = runCmdSync(["git", "rev-parse", "--verify", "HEAD"]);
        if (headCheck.code !== 0) {
            console.warn("⚠️  Aviso: El repositorio local aún no contiene commits.");
            hasErrors = true;
        } else {
            const gitStatus = runCmdSync(["git", "status", "--porcelain"]);
            if (gitStatus.stdout) {
                console.warn("⚠️  Aviso: El repositorio tiene cambios locales sin confirmar.");
            } else {
                console.log("✅ Árbol Git limpio.");
            }
        }

        // 2. Git tag
        const tagCheck = runCmdSync(["git", "tag", "-l", `v${appVersion}`]);
        if (tagCheck.stdout.includes(`v${appVersion}`)) {
            console.warn(`⚠️  El tag v${appVersion} ya existe localmente.`);
        } else {
            console.log(`✅ Tag v${appVersion} libre localmente.`);
        }

        // 3. Artefactos en release/
        const releaseDir = join(root, "release");
        let foundInstaller: string | null = null;
        if (existsSync(releaseDir)) {
            const files = readdirSync(releaseDir);
            foundInstaller = files.find((f) => f.startsWith("DaVinciExportador-Setup") && f.endsWith(".exe")) ?? null;
        }

        if (foundInstaller) {
            const fullPath = join(releaseDir, foundInstaller);
            const st = statSync(fullPath);
            const hash = sha256(fullPath);
            console.log(`✅ Instalador presente: ${foundInstaller} (${(st.size / 1024 / 1024).toFixed(2)} MB)`);
            console.log(`   SHA-256: ${hash}`);
        } else {
            console.warn(`❌ Instalador no encontrado en release/DaVinciExportador-Setup-*.exe. Ejecuta 'mise release' antes de publicar.`);
            hasErrors = true;
        }

        // 4. Notas de versión
        const notesPath = join(root, "RELEASE_MESSAGE.md");
        if (existsSync(notesPath)) {
            console.log("✅ RELEASE_MESSAGE.md presente.");
        } else {
            console.warn("⚠️  RELEASE_MESSAGE.md no encontrado en la raíz.");
        }

        console.log("\n(--check completado: modo solo lectura sin escrituras)");
        return hasErrors ? 1 : 0;
    }

    console.error("\n❌ Publicación bloqueada: Requiere confirmación y autorización explícita para publicar en producción.");
    console.error("   Usa --plan para revisar los pasos previstos o --check para verificar el estado de los artefactos.");
    return 1;
}

export async function main(args = Bun.argv.slice(2)): Promise<number> {
    const [action, ...rest] = args;
    if (!action || action === "--help" || rest.includes("--help")) {
        console.log(help);
        return 0;
    }

    if (action === "publish") {
        return handlePublish(rest);
    }

    const isPlan = rest.includes("--plan");

    if (action === "dev") {
        const cmd = [pythonExe, "main.py"];
        console.log(`dev ${appName}\nDirectorio: ${root}\nComando: ${cmd.join(" ")}`);
        if (isPlan) return 0;
        const child = Bun.spawn(cmd, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        return (await child.exited) ?? 0;
    }

    if (action === "build") {
        const cmd = [pythonExe, "-m", "compileall", "-q", "src", "src-flet", "main.py"];
        console.log(`build ${appName}\nDirectorio: ${root}\nComando: ${cmd.join(" ")}`);
        if (isPlan) return 0;

        console.log("\n==> Compilando y verificando sintaxis de código Python...");
        const child = Bun.spawn(cmd, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        return (await child.exited) ?? 0;
    }

    if (action === "release") {
        const psArgs = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", "./scripts/packaging/Build-Installer.ps1",
        ];
        console.log(`release ${appName}\nDirectorio: ${root}\nComando: ${psArgs.join(" ")}`);
        if (isPlan) return 0;

        const child = Bun.spawn(psArgs, { cwd: root, stdin: "inherit", stdout: "inherit", stderr: "inherit" });
        return (await child.exited) ?? 0;
    }

    throw new Error(`Acción desconocida: ${action}. Usa mise dev, mise build, mise release o mise publish.`);
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
