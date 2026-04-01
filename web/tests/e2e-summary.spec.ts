import { expect, test } from "@playwright/test";

test("summary flow mock smoke test", async ({ page }) => {
  // E2E 先用前端 mock 路由驗證頁面骨架與導航流程，避免依賴真 API。
  await page.route("**/api/v1/sources", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "src_1",
          name: "本地來源",
          type: "local",
          status: "ready",
          config: { path: "./samples/local_source" },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]
    });
  });

  await page.goto("/");
  await expect(page.getByText("智能辦公室工作台")).toBeVisible();
  await page.getByRole("link", { name: "資料源" }).click();
  await expect(page.getByText("本地資料源接入")).toBeVisible();
});
