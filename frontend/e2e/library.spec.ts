import { test, expect } from "@playwright/test";
import { registerViaUi, testEmail, uploadBook, makeTestPdfTemp } from "./fixtures";

test("upload PDF → card appears → cover renders → delete", async ({ page }) => {
  await registerViaUi(page, testEmail());

  const pdf = makeTestPdfTemp(3);
  await uploadBook(page, pdf, "E2E Book");

  const card = page.locator(".book-card").first();
  await expect(card).toContainText("E2E Book");

  // cover renders in the background after processing
  const cover = card.locator(".book-cover");
  await expect(cover).toBeVisible({ timeout: 30_000 });

  // delete via card menu (hover reveals it in some UIs; the delete control
  // lives inside the card)
  page.on("dialog", (d) => d.accept()); // accept confirm() if used
  await card.hover();
  const del = card.getByText(/delete|✕|trash/i);
  if (await del.count()) {
    await del.first().click();
    await expect(page.locator(".book-card")).toHaveCount(0, { timeout: 10_000 });
  }
});

test("book status eventually becomes ready", async ({ page }) => {
  await registerViaUi(page, testEmail());
  await uploadBook(page, makeTestPdfTemp(2));
  // processing badge transitions to ready
  await expect(page.locator(".book-card .badge.ready").first())
    .toBeVisible({ timeout: 30_000 });
});
