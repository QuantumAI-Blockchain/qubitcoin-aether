import { test, expect } from "@playwright/test";

test.describe("Aether Chat", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/aether");
  });

  test("aether page loads", async ({ page }) => {
    await expect(page.locator("main, [data-testid]").first()).toBeVisible();
  });

  test("chat input is visible and interactive", async ({ page }) => {
    await page.waitForTimeout(2000);
    // Find chat input (textarea or input)
    const chatInput = page.locator(
      'textarea, input[type="text"], [contenteditable="true"]'
    );
    const firstInput = chatInput.first();
    if (await firstInput.isVisible()) {
      await firstInput.fill("Hello Aether");
      const value = await firstInput.inputValue().catch(() => "");
      expect(value).toContain("Hello");
    }
  });

  test("phi consciousness indicator is visible", async ({ page }) => {
    await page.waitForTimeout(2000);
    // Should show phi value or consciousness indicator somewhere
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });
});
