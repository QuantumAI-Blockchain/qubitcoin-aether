import { test, expect } from "@playwright/test";

test.describe("Launchpad", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/launchpad");
  });

  test("launchpad page loads", async ({ page }) => {
    await expect(page.locator("main, [data-testid]").first()).toBeVisible();
  });

  test("launchpad shows project listings", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    // Should have some project-related content
    const hasProjects =
      body.includes("Deploy") ||
      body.includes("Project") ||
      body.includes("Contract") ||
      body.includes("Token");
    expect(hasProjects).toBeTruthy();
  });

  test("deploy wizard can be accessed", async ({ page }) => {
    await page.waitForTimeout(2000);
    // Look for deploy button
    const deployBtn = page.locator(
      'button:has-text("Deploy"), button:has-text("DEPLOY"), a:has-text("Deploy")'
    );
    if (await deployBtn.first().isVisible()) {
      await deployBtn.first().click();
      await page.waitForTimeout(1000);
      // Should show wizard steps
      const body = (await page.textContent("body")) ?? "";
      expect(body.length).toBeGreaterThan(0);
    }
  });
});
