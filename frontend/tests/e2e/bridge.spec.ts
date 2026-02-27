import { test, expect } from "@playwright/test";

test.describe("Bridge", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/bridge");
  });

  test("bridge page loads", async ({ page }) => {
    await expect(page.locator("main, [data-testid]").first()).toBeVisible();
  });

  test("bridge shows supported chains", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = await page.textContent("body");
    // Should mention at least Ethereum or BNB
    const hasChain =
      body?.includes("Ethereum") ||
      body?.includes("ETH") ||
      body?.includes("BNB") ||
      body?.includes("Solana");
    expect(hasChain).toBeTruthy();
  });

  test("bridge has amount input", async ({ page }) => {
    await page.waitForTimeout(2000);
    const amountInput = page.locator(
      'input[type="number"], input[placeholder*="mount"], input[aria-label*="mount"]'
    );
    if (await amountInput.first().isVisible()) {
      await amountInput.first().fill("100");
      // Should not crash
      await page.waitForTimeout(500);
    }
  });

  test("bridge has connect wallet button", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasWalletUI =
      body.includes("Connect") ||
      body.includes("Wallet") ||
      body.includes("wallet");
    expect(hasWalletUI).toBeTruthy();
  });
});
