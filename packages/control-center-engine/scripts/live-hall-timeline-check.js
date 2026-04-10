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
    if (message.type() === "error") errors.push(`console:${message.text()}`);
  });

  await page.goto("http://127.0.0.1:4310/?section=hall-chat", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.waitForSelector("[data-collaboration-hall-root]", { timeout: 30000 });

  await page.locator("[data-hall-compose-task]").click({ timeout: 10000 });
  await page.locator("[data-hall-composer-textarea]").fill("我想要做一个视频 介绍我的群聊功能");
  await page.locator("[data-hall-send-reply]").click({ timeout: 10000 });
  await wait(1000);

  await page.locator("[data-hall-composer-textarea]").fill("我想要做一个视频 介绍我的群聊功能");
  await page.locator("[data-hall-send-reply]").click({ timeout: 10000 });

  const timeline = [];
  for (let attempt = 1; attempt <= 12; attempt += 1) {
    await wait(5000);
    const authors = await page.locator(".hall-message .hall-message-author strong").allTextContents().catch(() => []);
    const bodies = await page
      .locator(".hall-message .hall-message-body")
      .evaluateAll((nodes) => nodes.map((node) => node.textContent || ""))
      .catch(() => []);
    const typing = await page.locator("[data-hall-typing-strip]").allTextContents().catch(() => []);
    timeline.push({
      t: attempt * 5,
      authors,
      typing,
      count: bodies.length,
      lastBodies: bodies.slice(-4),
    });
  }

  const selectedTaskCardId = await page
    .locator("[data-task-card-id][aria-current='page']")
    .first()
    .getAttribute("data-task-card-id")
    .catch(() => null);

  await page.screenshot({
    path: "/tmp/live-hall-timeline-check.png",
    fullPage: true,
  });

  console.log(
    JSON.stringify(
      {
        selectedTaskCardId,
        timeline,
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
