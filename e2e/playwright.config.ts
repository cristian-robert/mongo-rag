import { defineConfig, devices } from "@playwright/test";

/**
 * MongoRAG e2e configuration.
 *
 * The suite expects the dashboard at WEB_BASE_URL (default
 * http://localhost:3100) and the API at API_BASE_URL (default
 * http://localhost:8100). Spin up the local stack with `docker compose up`
 * before running the tests, or set the env vars to point at a deployed
 * preview environment.
 */
const WEB_BASE_URL = process.env.WEB_BASE_URL ?? "http://localhost:3100";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: WEB_BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
