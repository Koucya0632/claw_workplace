import { join } from "node:path";

export function getRuntimeDir(): string {
  const override = process.env.OPENCLAW_RUNTIME_DIR?.trim();
  return override ? override : join(process.cwd(), "runtime");
}

export function resolveRuntimePath(...parts: string[]): string {
  return join(getRuntimeDir(), ...parts);
}
