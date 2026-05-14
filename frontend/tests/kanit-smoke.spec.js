import { test, expect } from "@playwright/test";

test("Kanıt ana akış smoke", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("Failed to load resource")) {
      errors.push(message.text());
    }
  });

  await page.goto("http://127.0.0.1:5174/", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: /Her kalite hatası/ })).toBeVisible();
  await expect(page.getByText("Beceri Yakınsama").first()).toBeVisible();

  await page.getByRole("button", { name: "Demoyu Gör" }).first().click();
  await expect(page.getByRole("heading", { name: /3 olay/ })).toBeVisible();

  await page.getByRole("button", { name: /Vardiya demosu/ }).click();
  await page.waitForTimeout(5200);
  await expect(page.getByText("Mentor onayı bekleniyor")).toBeVisible();

  expect(errors).toEqual([]);
});
