import { defineConfig } from "@playwright/test";

// E2E tests run against the running app (Docker compose at :8080, or the local
// uvicorn stand-in at :8017 — set BASE_URL to pick). Not started by Playwright:
// `reuseExistingServer` keeps it simple, start the stack yourself first.
const BASE_URL = process.env.BASE_URL ?? "http://localhost:4173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // shared backend state; keep tests sequential
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
