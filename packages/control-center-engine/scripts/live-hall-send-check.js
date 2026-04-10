const { chromium } = require("playwright");

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

  await page.locator("[data-hall-compose-task]").click({ timeout: 10000 });
  await page.locator("[data-hall-composer-textarea]").fill("我想要做一个视频 介绍我的群聊功能");
  await page.locator("[data-hall-composer-textarea]").press("Enter", { timeout: 10000 });
  await wait(1000);

  const selectedTaskCardId = await page
    .locator("[data-task-card-id][aria-current='page']")
    .first()
    .getAttribute("data-task-card-id")
    .catch(() => null);

  await page.locator("[data-hall-composer-textarea]").fill("我想要做一个视频 介绍我的群聊功能");
  await page.locator("[data-hall-composer-textarea]").press("Enter", { timeout: 10000 });

  let typingSeen = false;
  let typingSnapshots = [];
  for (let attempt = 0; attempt < 8; attempt += 1) {
    typingSnapshots = await page.locator("[data-hall-typing-strip]").allTextContents().catch(() => []);
    if (typingSnapshots.some((text) => String(text || "").trim().length > 0)) {
      typingSeen = true;
      break;
    }
    await wait(1000);
  }

  let replySeen = false;
  let authors = [];
  for (let attempt = 0; attempt < 35; attempt += 1) {
    authors = await page
      .locator(".hall-message .hall-message-author strong")
      .allTextContents()
      .catch(() => []);
    if (authors.some((label) => !String(label || "").includes("Operator"))) {
      replySeen = true;
      break;
    }
    await wait(1000);
  }

  const messageCount = await page.locator(".hall-message").count();
  const bodies = await page
    .locator(".hall-message .hall-message-body")
    .evaluateAll((nodes) => nodes.map((node) => node.textContent || ""))
    .catch(() => []);
  const pendingTyping = await page.locator("[data-hall-typing-strip]").allTextContents().catch(() => []);
  const headerStage = await page.locator("[data-hall-thread-meta]").textContent().catch(() => null);
  const title = await page.locator("[data-hall-thread-title]").textContent().catch(() => null);

  await page.screenshot({
    path: "/tmp/live-hall-send-check.png",
    fullPage: true,
  });

  console.log(
    JSON.stringify(
      {
        title,
        headerStage,
        selectedTaskCardId,
        typingSeen,
        typingSnapshots,
        replySeen,
        messageCount,
        authors,
        pendingTyping,
        bodies: bodies.slice(0, 10),
        errors,
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
