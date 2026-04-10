const { chromium } = require("playwright");

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
  const rawHtml = await page.content();
  const hasHallRoot = rawHtml.includes("data-collaboration-hall-root");
  if (!hasHallRoot) {
    console.log(
      JSON.stringify(
        {
          currentUrl: page.url(),
          pageTitle: await page.title(),
          hasHallRoot,
          htmlSample: rawHtml.slice(0, 1200),
          errors,
        },
        null,
        2,
      ),
    );
    await browser.close();
    return;
  }

  await page.waitForSelector("[data-collaboration-hall-root]", { timeout: 30000, state: "attached" });
  await page.waitForTimeout(1500);

  const initialHeadline = await page.locator("[data-hall-headline]").textContent().catch(() => null);
  const initialTitle = await page.locator("[data-hall-thread-title]").textContent().catch(() => null);
  const cards = page.locator("[data-task-card-id]");
  const cardCount = await cards.count();
  const selectedCardIdBefore = await page
    .locator("[data-task-card-id][aria-current='page']")
    .first()
    .getAttribute("data-task-card-id")
    .catch(() => null);
  const initialBodyNodes = await page
    .locator(".hall-message-body")
    .evaluateAll((nodes) => nodes.slice(0, 3).map((node) => node.innerHTML));

  let switchedTitle = null;
  let selectedCardIdAfter = null;
  if (cardCount > 1) {
    await cards.nth(1).click({ timeout: 10000 });
    await page.waitForTimeout(800);
    switchedTitle = await page.locator("[data-hall-thread-title]").textContent().catch(() => null);
    selectedCardIdAfter = await page
      .locator("[data-task-card-id][aria-current='page']")
      .first()
      .getAttribute("data-task-card-id")
      .catch(() => null);
  }

  await page.locator("[data-hall-compose-task]").click({ timeout: 10000 });
  await page.waitForTimeout(600);

  const composerState = await page.evaluate(() => ({
    mounted: !!document.querySelector("[data-collaboration-hall-root]"),
    taskMode: document
      .querySelector("[data-collaboration-hall-root]")
      ?.classList.contains("is-composing-task"),
    placeholder:
      document.querySelector("[data-hall-composer-textarea]")?.getAttribute("placeholder") || null,
    headline: document.querySelector("[data-hall-headline]")?.textContent || null,
  }));

  const bodyNodesAfterSwitch = await page
    .locator(".hall-message-body")
    .evaluateAll((nodes) => nodes.slice(0, 3).map((node) => node.innerHTML));

  await page.screenshot({
    path: "/tmp/hall4310_browser_check.png",
    fullPage: true,
  });

  console.log(
    JSON.stringify(
      {
        initialHeadline,
        initialTitle,
        currentUrl: page.url(),
        pageTitle: await page.title(),
        hasHallRoot,
        cardCount,
        selectedCardIdBefore,
        switchedTitle,
        selectedCardIdAfter,
        initialBodyNodes,
        composerState,
        bodyNodesAfterSwitch,
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
