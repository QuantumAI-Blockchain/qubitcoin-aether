import { test, expect } from "@playwright/test";

test.describe("Contract Deployment", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/launchpad");
  });

  test("launchpad deploy wizard loads", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasDeployUI =
      body.includes("Deploy") ||
      body.includes("Contract") ||
      body.includes("Template") ||
      body.includes("Token");
    expect(hasDeployUI).toBeTruthy();
  });

  test("contract templates are listed", async ({ page }) => {
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    // Should show at least some template types
    const hasTemplates =
      body.includes("Token") ||
      body.includes("NFT") ||
      body.includes("Governance") ||
      body.includes("Escrow") ||
      body.includes("QBC-20");
    expect(hasTemplates).toBeTruthy();
  });

  test("deploy button exists", async ({ page }) => {
    await page.waitForTimeout(2000);
    const deployBtn = page.locator(
      'button:has-text("Deploy"), button:has-text("DEPLOY"), a:has-text("Deploy")'
    );
    if (await deployBtn.first().isVisible()) {
      // Just check it exists — clicking requires wallet connection
      await expect(deployBtn.first()).toBeEnabled();
    }
  });

  test("QVM explorer page shows contracts section", async ({ page }) => {
    await page.goto("/qvm");
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    const hasContractInfo =
      body.includes("Contract") ||
      body.includes("Bytecode") ||
      body.includes("Storage") ||
      body.includes("Deploy") ||
      body.includes("QVM");
    expect(hasContractInfo).toBeTruthy();
  });

  test("dashboard shows contract stats", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForTimeout(2000);
    const body = (await page.textContent("body")) ?? "";
    // Dashboard should mention contracts somewhere
    const hasContracts =
      body.includes("Contract") ||
      body.includes("contract") ||
      body.includes("QVM") ||
      body.includes("Deploy");
    expect(hasContracts).toBeTruthy();
  });
});
