import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("landing page loads and has title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/qubitcoin/i);
  });

  test("landing page has key sections", async ({ page }) => {
    await page.goto("/");
    // Hero section should be visible
    await expect(page.locator("main")).toBeVisible();
    // Should have navigation
    await expect(page.locator("nav, header")).toBeVisible();
  });

  test.describe("all pages load without errors", () => {
    const pages = [
      { path: "/", name: "Landing" },
      { path: "/explorer", name: "Explorer" },
      { path: "/aether", name: "Aether" },
      { path: "/bridge", name: "Bridge" },
      { path: "/exchange", name: "Exchange" },
      { path: "/launchpad", name: "Launchpad" },
      { path: "/dashboard", name: "Dashboard" },
      { path: "/wallet", name: "Wallet" },
      { path: "/qvm", name: "QVM" },
    ];

    for (const p of pages) {
      test(`${p.name} page (${p.path}) loads`, async ({ page }) => {
        const errors: string[] = [];
        page.on("pageerror", (err) => errors.push(err.message));

        const response = await page.goto(p.path, {
          waitUntil: "domcontentloaded",
        });
        expect(response?.status()).toBeLessThan(500);
        // Allow up to 5s for client hydration
        await page.waitForTimeout(1000);
        // No uncaught JS errors
        expect(errors).toHaveLength(0);
      });
    }
  });

  test("navigation links work", async ({ page }) => {
    await page.goto("/");

    // Find and click explorer link
    const explorerLink = page.locator('a[href="/explorer"]').first();
    if (await explorerLink.isVisible()) {
      await explorerLink.click();
      await expect(page).toHaveURL(/\/explorer/);
    }
  });
});
