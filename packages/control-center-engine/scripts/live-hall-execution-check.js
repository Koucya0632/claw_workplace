const { chromium } = require("playwright");

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForPlanButton(page, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const count = await page.locator("[data-hall-plan-order]").count().catch(() => 0);
    if (count > 0) return true;
    await wait(2000);
  }
  return false;
}

async function askForPlanButton(page) {
  await page.locator("[data-hall-composer-textarea]").fill("请收口并安排执行顺序，然后开始执行。");
  await page.locator("[data-hall-send-reply]").click();
}

async function ensureOrderParticipant(page, participantId) {
  const chip = page.locator(`[data-hall-order-add="${participantId}"]`).first();
  if (await chip.count()) {
    await chip.click();
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } });
  const errors = [];

  page.on("pageerror", (error) => errors.push(`pageerror:${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(`console:${message.text()}`);
    }
  });

  await page.goto("http://127.0.0.1:4310/?section=hall-chat", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.waitForSelector("[data-collaboration-hall-root]", { timeout: 30000 });

  await page.locator("[data-hall-compose-task]").click();
  await page
    .locator("[data-hall-composer-textarea]")
    .fill("请先扫描 control-center 代码，找出 hall-chat 的 3 个关键入口文件，并说明每个文件负责什么。");
  await page.locator("[data-hall-send-reply]").click();

  let hasPlanButton = await waitForPlanButton(page, 45000);
  if (!hasPlanButton) {
    await askForPlanButton(page);
    hasPlanButton = await waitForPlanButton(page, 45000);
  }
  if (!hasPlanButton) {
    throw new Error("plan-order button did not appear");
  }

  await page.locator("[data-hall-plan-order]").first().click();
  await page.waitForSelector("[data-hall-order-save]", { timeout: 20000 });

  await ensureOrderParticipant(page, "pandas");
  await ensureOrderParticipant(page, "main");
  await ensureOrderParticipant(page, "otter");

  await page
    .locator('[data-hall-item-task="pandas"]')
    .fill("扫描 control-center 代码，至少贴出 3 个真实文件路径，并说明每个文件负责什么。");
  await page.locator('[data-hall-item-handoff-to="pandas"]').selectOption("main");
  await page
    .locator('[data-hall-item-handoff="pandas"]')
    .fill("贴完 3 个文件路径和职责后交给 @main 评审是否够准确。");

  await page
    .locator('[data-hall-item-task="main"]')
    .fill("只检查 pandas 列的文件是否真的关键、解释是否准确；不重做扫描。");
  await page.locator('[data-hall-item-handoff-to="main"]').selectOption("otter");
  await page
    .locator('[data-hall-item-handoff="main"]')
    .fill("确认关键文件没问题后交给 @otter 只挑 must-fix。");

  await page.locator('[data-hall-item-task="otter"]').fill("只挑 must-fix，别扩 scope。");
  await page.locator('[data-hall-item-handoff-to="otter"]').selectOption("");
  await page.locator('[data-hall-item-handoff="otter"]').fill("没有 must-fix 就请老板评审。");

  await page.locator("[data-hall-order-save]").click();
  await page.waitForTimeout(2500);

  const startButton = page.locator("[data-hall-start-execution]").first();
  if (await startButton.count()) {
    await startButton.click();
  } else {
    throw new Error("start execution button did not appear after saving order");
  }

  const timeline = [];
  for (let attempt = 1; attempt <= 18; attempt += 1) {
    await wait(5000);
    const authors = await page.locator(".hall-message .hall-message-author strong").allTextContents().catch(() => []);
    const bodies = await page
      .locator(".hall-message .hall-message-body")
      .evaluateAll((nodes) => nodes.map((node) => node.textContent || ""))
      .catch(() => []);
    const stage = await page.locator("[data-hall-thread-meta]").textContent().catch(() => null);
    timeline.push({
      t: attempt * 5,
      stage,
      authors,
      lastBodies: bodies.slice(-6),
    });
  }

  const finalBodies = timeline.at(-1)?.lastBodies || [];
  const hasVisibleFilePath = finalBodies.some((body) => /src\/ui\/collaboration-hall\.ts|src\/runtime\/collaboration-hall-orchestrator\.ts|src\/runtime\/hall-runtime-dispatch\.ts/.test(body));
  const hasWrongHandoffWarning = timeline.some((entry) =>
    entry.lastBodies.some((body) => body.includes("Handoff moved to")),
  );
  const visibleMessages = await page
    .locator(".hall-message .hall-message-body")
    .evaluateAll((nodes) => nodes.map((node) => ({
      text: node.textContent || "",
      lineClamp: getComputedStyle(node).webkitLineClamp,
      overflow: getComputedStyle(node).overflow,
      whiteSpace: getComputedStyle(node).whiteSpace,
      display: getComputedStyle(node).display,
    })))
    .catch(() => []);

  console.log(
    JSON.stringify(
      {
        errors,
        timeline,
        hasVisibleFilePath,
        hasWrongHandoffWarning,
        visibleMessages: visibleMessages.slice(-4),
      },
      null,
      2,
    ),
  );

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
