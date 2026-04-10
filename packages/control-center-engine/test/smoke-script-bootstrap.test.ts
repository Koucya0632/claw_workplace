import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("hall smoke bootstrap installs playwright package and chromium when missing", async () => {
  const [helperSource, hallSmokeSource] = await Promise.all([
    readFile("scripts/ensure-playwright.js", "utf8"),
    readFile("scripts/hall-release-smoke.ts", "utf8"),
  ]);

  assert(helperSource.includes('npmCommand()'));
  assert(helperSource.includes('["install", "--no-save", "playwright"]'));
  assert(helperSource.includes('[cliPath, "install", "chromium"]'));
  assert(helperSource.includes('playwright.chromium.launch({ headless: true })'));
  assert(hallSmokeSource.includes('const helperModule = await import("./ensure-playwright.js");'));
  assert(hallSmokeSource.includes('helperModule.ensurePlaywrightChromium ??'));
  assert(hallSmokeSource.includes("await ensureBrowserAutomation();"));
});
