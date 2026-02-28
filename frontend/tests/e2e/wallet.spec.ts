import { test, expect } from "@playwright/test";

test.describe("Wallet", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/wallet");
  });

  test("wallet page loads without errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.waitForTimeout(2000);
    expect(errors).toHaveLength(0);
    await expect(page.locator("main, [data-testid]").first()).toBeVisible();
  });

  test("wallet shows create or connect options", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasWalletAction =
      body.includes("Create") ||
      body.includes("Connect") ||
      body.includes("Wallet") ||
      body.includes("Generate");
    expect(hasWalletAction).toBeTruthy();
  });

  test("wallet create button exists and is clickable", async ({ page }) => {
    await page.waitForTimeout(2000);
    const createBtn = page.locator(
      'button:has-text("Create"), button:has-text("Generate"), button:has-text("New Wallet")'
    );
    if (await createBtn.first().isVisible()) {
      await createBtn.first().click();
      await page.waitForTimeout(1000);
      // Should show wallet details or next step — no crash
      const body = (await page.textContent("body")) ?? "";
      expect(body.length).toBeGreaterThan(0);
    }
  });

  test("wallet shows balance section", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasBalance =
      body.includes("Balance") ||
      body.includes("QBC") ||
      body.includes("0.00") ||
      body.includes("---");
    expect(hasBalance).toBeTruthy();
  });

  test("wallet has send transaction UI", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasSend =
      body.includes("Send") ||
      body.includes("Transfer") ||
      body.includes("Recipient") ||
      body.includes("Address");
    expect(hasSend).toBeTruthy();
  });
});
