import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests of the core demo flow (e2e/). They sign in with the demo accounts (fixed OTP 123456, no SMS),
 * so they need a backend whose database has the demo seed.
 *
 * E2E_BASE_URL: the web app to test, e.g. the deployed site (https://...vercel.app). Without it the Vite dev
 * server is started on :5173 (it proxies /api to the backend at API_PROXY, default http://localhost:8000).
 * E2E_CHAT=1 also sends one real message to the AI assistant (non-deterministic and paid, so off by default).
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  // The demo accounts are shared: one worker keeps the runs from stepping on each other
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run dev -- --port 5173 --strictPort",
        url: "http://localhost:5173",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
