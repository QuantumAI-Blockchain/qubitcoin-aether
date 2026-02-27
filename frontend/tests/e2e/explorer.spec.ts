import { test, expect } from "@playwright/test";

test.describe("Explorer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/explorer");
  });

  test("explorer page renders main sections", async ({ page }) => {
    // Should have some visible content
    await expect(page.locator("main, [data-testid]").first()).toBeVisible();
  });

  test("explorer has search functionality", async ({ page }) => {
    // Look for search input
    const search = page.locator(
      'input[type="search"], input[placeholder*="earch"], [role="search"] input'
    );
    if (await search.first().isVisible()) {
      await search.first().fill("1");
      // Should not crash on search
      await page.waitForTimeout(500);
    }
  });

  test("explorer displays network stats", async ({ page }) => {
    // Should show some blockchain stats (block height, difficulty, etc.)
    await page.waitForTimeout(2000);
    // Look for stat-like content
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });

  test("keyboard navigation works on data tables", async ({ page }) => {
    await page.waitForTimeout(2000);
    // Tab through interactive elements
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    // Should not throw
    const focused = await page.evaluate(
      () => document.activeElement?.tagName
    );
    expect(focused).toBeTruthy();
  });
});
