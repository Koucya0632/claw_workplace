"use strict";

const { execFileSync } = require("node:child_process");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");

function npmCommand() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function installPlaywrightPackageIfMissing() {
  try {
    return {
      packageJsonPath: require.resolve("playwright/package.json"),
      installedPackage: false,
    };
  } catch {
    console.log("[smoke] playwright package missing; installing a local temporary copy...");
    execFileSync(npmCommand(), ["install", "--no-save", "playwright"], {
      cwd: ROOT,
      stdio: "inherit",
    });
    return {
      packageJsonPath: require.resolve("playwright/package.json"),
      installedPackage: true,
    };
  }
}

function shouldInstallChromium(error) {
  const message = String(error instanceof Error ? error.message : error || "");
  return (
    message.includes("Executable doesn't exist") ||
    message.includes("browserType.launch") ||
    message.includes("Please run the following command") ||
    message.includes("playwright install")
  );
}

async function ensurePlaywrightChromium() {
  const { packageJsonPath, installedPackage } = installPlaywrightPackageIfMissing();
  const playwright = require("playwright");
  let browser = null;
  try {
    browser = await playwright.chromium.launch({ headless: true });
    await browser.close();
    return { installedPackage, installedBrowser: false };
  } catch (error) {
    if (browser) {
      try { await browser.close(); } catch {}
    }
    if (!shouldInstallChromium(error)) throw error;
  }

  console.log("[smoke] chromium browser missing; installing Playwright Chromium...");
  const cliPath = path.join(path.dirname(packageJsonPath), "cli.js");
  execFileSync(process.execPath, [cliPath, "install", "chromium"], {
    cwd: ROOT,
    stdio: "inherit",
  });

  browser = await playwright.chromium.launch({ headless: true });
  await browser.close();
  return { installedPackage, installedBrowser: true };
}

module.exports = {
  ensurePlaywrightChromium,
};
