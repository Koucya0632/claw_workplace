import { mkdtemp, readdir, rm } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(scriptDir, "..");

async function main(): Promise<void> {
  const testArgs = process.argv.slice(2);
  const targets = testArgs.length > 0 ? testArgs : await collectTestFiles(resolve(packageRoot, "test"));
  const runtimeDir = await mkdtemp(join(tmpdir(), "openclaw-control-center-test-"));

  try {
    const exitCode = await runNodeTests(targets, runtimeDir);
    process.exitCode = exitCode;
  } finally {
    await rm(runtimeDir, { recursive: true, force: true });
  }
}

async function collectTestFiles(rootDir: string): Promise<string[]> {
  const output: string[] = [];
  await walk(rootDir, output);
  return output.sort();
}

async function walk(dir: string, output: string[]): Promise<void> {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      await walk(fullPath, output);
      continue;
    }
    if (entry.isFile() && entry.name.endsWith(".test.ts")) {
      output.push(fullPath);
    }
  }
}

function runNodeTests(targets: string[], runtimeDir: string): Promise<number> {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(
      process.execPath,
      ["--import", "tsx", "--test", "--test-concurrency=1", ...targets],
      {
        cwd: packageRoot,
        env: {
          ...process.env,
          OPENCLAW_RUNTIME_DIR: runtimeDir,
        },
        stdio: "inherit",
      },
    );
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (signal) {
        resolvePromise(1);
        return;
      }
      resolvePromise(code ?? 0);
    });
  });
}

void main();
