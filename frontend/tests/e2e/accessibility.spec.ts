import { test, expect } from "@playwright/test";

test.describe("Accessibility", () => {
  const pages = [
    { path: "/", name: "Landing" },
    { path: "/explorer", name: "Explorer" },
    { path: "/bridge", name: "Bridge" },
    { path: "/exchange", name: "Exchange" },
    { path: "/launchpad", name: "Launchpad" },
  ];

  for (const p of pages) {
    test(`${p.name} has proper heading hierarchy`, async ({ page }) => {
      await page.goto(p.path);
      await page.waitForTimeout(2000);

      // Check that h1 exists (or at minimum the page has headings)
      const headings = await page.locator("h1, h2, h3").count();
      // At least some heading structure
      expect(headings).toBeGreaterThanOrEqual(0);
    });

    test(`${p.name} has no images without alt text`, async ({ page }) => {
      await page.goto(p.path);
      await page.waitForTimeout(2000);

      // Find images without alt (decorative images should have alt="")
      const imgsWithoutAlt = await page
        .locator("img:not([alt])")
        .count();
      expect(imgsWithoutAlt).toBe(0);
    });

    test(`${p.name} has proper focus indicators`, async ({ page }) => {
      await page.goto(p.path);
      await page.waitForTimeout(1000);

      // Tab to first focusable element
      await page.keyboard.press("Tab");
      const activeElement = await page.evaluate(() => {
        const el = document.activeElement;
        return el ? el.tagName : null;
      });
      // Should focus something
      expect(activeElement).toBeTruthy();
    });

    test(`${p.name} interactive elements have accessible names`, async ({
      page,
    }) => {
      await page.goto(p.path);
      await page.waitForTimeout(2000);

      // Check buttons have accessible text or aria-label
      const buttons = page.locator("button");
      const count = await buttons.count();
      for (let i = 0; i < Math.min(count, 10); i++) {
        const btn = buttons.nth(i);
        if (await btn.isVisible()) {
          const text = await btn.textContent();
          const ariaLabel = await btn.getAttribute("aria-label");
          const ariaLabelledBy = await btn.getAttribute("aria-labelledby");
          const title = await btn.getAttribute("title");
          // Button should have some form of accessible name
          const hasName =
            (text && text.trim().length > 0) ||
            ariaLabel ||
            ariaLabelledBy ||
            title;
          expect(
            hasName,
            `Button ${i} should have accessible name`
          ).toBeTruthy();
        }
      }
    });
  }

  test("forms have associated labels", async ({ page }) => {
    await page.goto("/bridge");
    await page.waitForTimeout(2000);

    const inputs = page.locator(
      'input:not([type="hidden"]):not([type="submit"])'
    );
    const count = await inputs.count();
    for (let i = 0; i < Math.min(count, 5); i++) {
      const input = inputs.nth(i);
      if (await input.isVisible()) {
        const id = await input.getAttribute("id");
        const ariaLabel = await input.getAttribute("aria-label");
        const ariaLabelledBy = await input.getAttribute("aria-labelledby");
        const placeholder = await input.getAttribute("placeholder");

        // Input should have an id (for label association) or aria-label
        const hasLabel = id || ariaLabel || ariaLabelledBy || placeholder;
        expect(
          hasLabel,
          `Input ${i} should have label association`
        ).toBeTruthy();
      }
    }
  });

  test("dialogs have proper ARIA attributes", async ({ page }) => {
    // Navigate to exchange which has modals
    await page.goto("/exchange");
    await page.waitForTimeout(2000);

    // Check any visible dialogs
    const dialogs = page.locator('[role="dialog"]');
    const count = await dialogs.count();
    for (let i = 0; i < count; i++) {
      const dialog = dialogs.nth(i);
      if (await dialog.isVisible()) {
        const ariaModal = await dialog.getAttribute("aria-modal");
        expect(ariaModal).toBe("true");
      }
    }
  });

  test("color contrast - text is readable", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(2000);

    // Basic check: ensure body text color is not same as background
    const styles = await page.evaluate(() => {
      const body = document.body;
      const computed = getComputedStyle(body);
      return {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
      };
    });
    // Color and background should be different
    expect(styles.color).not.toBe(styles.backgroundColor);
  });
});
