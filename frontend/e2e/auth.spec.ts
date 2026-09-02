import { test, expect } from "@playwright/test";
import { registerViaUi, testEmail } from "./fixtures";

test("register a new account lands on library", async ({ page }) => {
  await registerViaUi(page, testEmail());
  await expect(page).toHaveURL(/\/$/); // library root
});

test("register duplicate email shows error", async ({ page }) => {
  const email = testEmail();
  await registerViaUi(page, email);

  // sign out, then try registering the same email again
  await page.getByRole("button", { name: /sign out/i }).click();
  await page.goto("/register");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password (min 8 chars)").fill("password123");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.locator(".error-msg")).toContainText(/already exists/i);
});

test("login with wrong password shows error", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("Email").fill("nobody@example.com");
  await page.getByPlaceholder("Password").fill("wrongpassword");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".error-msg")).toContainText(/invalid/i);
});

test("register → sign out → login works", async ({ page }) => {
  const email = testEmail();
  await registerViaUi(page, email);
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/login/);

  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password").fill("password123");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText("Upload PDF")).toBeVisible({ timeout: 15_000 });
});
