import { test, expect } from "@playwright/test";
import { registerViaUi, testEmail, uploadBook, makeTestPdfTemp } from "./fixtures";

async function openReader(page: import("@playwright/test").Page) {
  await registerViaUi(page, testEmail());
  await uploadBook(page, makeTestPdfTemp(4));
  await expect(page.locator(".book-card .badge.ready").first())
    .toBeVisible({ timeout: 30_000 });
  await page.locator(".book-card").first().click();
  await expect(page.locator(".pdf-pane")).toBeVisible({ timeout: 20_000 });
  // pdf.js renders at least one page canvas
  await expect(page.locator(".pdf-pane canvas").first())
    .toBeVisible({ timeout: 20_000 });
}

test("reader opens: pages render, page counter visible", async ({ page }) => {
  await openReader(page);
  await expect(page.locator(".pdf-page-num")).toContainText(/p\. 1/);
  await expect(page.locator("text=No embedded outline")).toBeVisible();
});

test("outline: add entry, jump works, edit it, delete it", async ({ page }) => {
  await openReader(page);

  // add
  await page.getByRole("button", { name: /＋ add/i }).click();
  await page.getByPlaceholder("Title").fill("Chapter One");
  await page.getByPlaceholder(/page \(1-/i).fill("2");
  await page.locator(".sidebar").getByRole("button", { name: /^add$/i }).click();
  const item = page.locator(".chapter-item", { hasText: "Chapter One" });
  await expect(item).toBeVisible();

  // clicking it jumps to page 2
  await item.click();
  await expect(page.locator(".pdf-page-num")).toContainText(/p\. 2/);

  // edit title
  await item.getByText("✎").click();
  await page.locator(".sidebar input").first().fill("Chapter One (edited)");
  await page.getByRole("button", { name: /^save$/i }).click();
  await expect(page.locator(".chapter-item", { hasText: "Chapter One (edited)" }))
    .toBeVisible();

  // delete
  await page.locator(".chapter-item", { hasText: "Chapter One (edited)" })
    .getByText("✕").click();
  await expect(page.locator(".chapter-item")).toHaveCount(0);
});

test("outline: save into PDF succeeds", async ({ page }) => {
  await openReader(page);
  await page.getByRole("button", { name: /＋ add/i }).click();
  await page.getByPlaceholder("Title").fill("Saved Chapter");
  await page.getByPlaceholder(/page \(1-/i).fill("1");
  await page.locator(".sidebar").getByRole("button", { name: /^add$/i }).click();
  await expect(page.locator(".chapter-item", { hasText: "Saved Chapter" })).toBeVisible();

  await page.getByRole("button", { name: /save into pdf/i }).click();
  await expect(page.locator(".sidebar").getByText(/bookmarks? written/i))
    .toBeVisible({ timeout: 20_000 });
});
