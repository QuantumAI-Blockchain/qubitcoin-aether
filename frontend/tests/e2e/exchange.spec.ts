import { test, expect } from "@playwright/test";

test.describe("Exchange", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/exchange");
  });

  test("exchange page loads", async ({ page }) => {
    await expect(page.locator("main, [data-testid]").first()).toBeVisible();
  });

  test("exchange shows trading pairs", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = await page.textContent("body");
    // Should mention QBC trading pair
    const hasPair =
      body?.includes("QBC") ||
      body?.includes("QUSD") ||
      body?.includes("BTC");
    expect(hasPair).toBeTruthy();
  });

  test("order book is visible", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasOrderBook =
      body.includes("Order") ||
      body.includes("Bid") ||
      body.includes("Ask") ||
      body.includes("Price");
    expect(hasOrderBook).toBeTruthy();
  });

  test("order entry form exists", async ({ page }) => {
    await page.waitForTimeout(2000);
    // Should have buy/sell buttons or tabs
    const body = (await page.textContent("body")) ?? "";
    const hasTrading =
      body.includes("Buy") ||
      body.includes("Sell") ||
      body.includes("BUY") ||
      body.includes("SELL");
    expect(hasTrading).toBeTruthy();
  });
});
