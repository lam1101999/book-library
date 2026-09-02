/**
 * Shared E2E helpers: unique test user registration + small PDF factory.
 * E2E runs against a real backend, so every test creates its own user to
 * avoid cross-test interference.
 */
import { Page, expect } from "@playwright/test";
import { execSync } from "node:child_process";
import { writeFileSync, mkdtempSync, mkdirSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";

const PYPDF_PY = "/opt/data/workspace/book-library/backend/.venv/bin/python";
// On other machines fall back to system python3 with pypdf installed
const PY = execSync(`command -v ${PYPDF_PY} >/dev/null 2>&1 && echo ${PYPDF_PY} || echo python3`)
  .toString().trim();

export function makeTestPdf(path: string, pages = 3): void {
  execSync(
    `${PY} -c "from pypdf import PdfWriter; w = PdfWriter(); ` +
    `[w.add_blank_page(width=400, height=600) for _ in range(${pages})]; ` +
    `w.write('${path}')"`,
  );
}

let tmp: string | null = null;
export function makeTestPdfTemp(pages = 3): string {
  tmp ??= mkdtempSync(join(tmpdir(), "bl-e2e-"));
  const p = join(tmp, `test-${Math.random().toString(36).slice(2)}.pdf`);
  makeTestPdf(p, pages);
  return p;
}

export function testEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;
}

export async function registerViaUi(page: Page, email: string, password = "password123") {
  await page.goto("/register");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password (min 8 chars)").fill(password);
  // button text on the register page is "Create account"
  await page.getByRole("button", { name: /create account/i }).click();
  // successful registration lands on the library page
  await expect(page.getByText("Upload PDF")).toBeVisible({ timeout: 15_000 });
}

export async function uploadBook(page: Page, filePath: string, title?: string) {
  // rename the file to encode the desired title (UI uses filename stem as title)
  if (title) {
    const dir = join(dirname(filePath), "renamed");
    mkdirSync(dir, { recursive: true });
    const newPath = join(dir, `${title}.pdf`);
    copyFileSync(filePath, newPath);
    filePath = newPath;
  }
  await page.setInputFiles('input[type="file"]', filePath);
  await expect(page.locator(".book-card").first()).toBeVisible({ timeout: 30_000 });
}
