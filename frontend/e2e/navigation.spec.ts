import { expect, test } from "@playwright/test";

test("owner can reach pass and shelter can reach registry", async ({ page }) => {
  await page.goto("/owner/history");
  await expect(page.getByRole("heading", { name: "Care history" })).toBeVisible();
  await page.getByRole("link", { name: "Share history" }).click();
  await expect(page.getByRole("heading", { name: "Share your care history" })).toBeVisible();
  await page.getByRole("link", { name: /Switch to shelter view/ }).click();
  await expect(page.getByRole("heading", { name: "Active records" })).toBeVisible();
  await page.getByRole("link", { name: "Pet registry" }).click();
  await expect(page.getByRole("heading", { name: "Pet registry" })).toBeVisible();
});

test("mobile navigation remains keyboard reachable", async ({ page }) => {
  await page.goto("/owner/history");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
});
