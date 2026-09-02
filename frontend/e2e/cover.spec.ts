import { test, expect } from "@playwright/test";
import { registerViaUi, testEmail, uploadBook, makeTestPdfTemp } from "./fixtures";

test("user sees the book cover on the library card", async ({ page }) => {
  await registerViaUi(page, testEmail());
  await uploadBook(page, makeTestPdfTemp(2), "Cover Vision");

  const card = page.locator(".book-card").first();
  const cover = card.locator(".book-cover");

  // cover <img> appears and actually loads (naturalWidth > 0 proves the
  // browser fetched a real PNG, not a broken/404 image)
  await expect(cover).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(async () => cover.evaluate((img: HTMLImageElement) => img.naturalWidth), {
      timeout: 15_000,
      message: "cover image should fully load (naturalWidth > 0)",
    })
    .toBeGreaterThan(0);

  // cover persists after a page reload (server-side file, not just in-memory)
  await page.reload();
  await expect(page.locator(".book-card .book-cover").first())
    .toBeVisible({ timeout: 30_000 });
});
