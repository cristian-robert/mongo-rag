/**
 * Happy-path e2e: signup → upload document → ask a question.
 *
 * Skipped by default. Set E2E=1 in the environment to run, after starting
 * the local stack with `docker compose up` or pointing WEB_BASE_URL /
 * API_BASE_URL at a live preview environment.
 *
 * The test is parameterised over the credentials in env vars below; falling
 * back to throwaway local-only values when run against a fresh stack.
 */

import { expect, test } from "@playwright/test";

const E2E_ENABLED = process.env.E2E === "1";
const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8100";

const TEST_EMAIL =
  process.env.TEST_USER_EMAIL ?? `e2e+${Date.now()}@mongorag.test`;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD ?? "supersecret-e2e-pw";
const TEST_ORG = process.env.TEST_ORG_NAME ?? "E2E Org";

test.describe("happy path", () => {
  test.skip(!E2E_ENABLED, "E2E=1 not set — skipping live e2e suite");

  test("the API is reachable before we exercise the UI", async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/health`);
    expect(response.ok(), `health: ${response.status()}`).toBe(true);
  });

  test("a new tenant can sign up, upload a document, and chat", async ({ page, request }) => {
    // ---- Signup ----------------------------------------------------------
    await page.goto("/signup");
    await page.getByLabel(/email/i).fill(TEST_EMAIL);
    await page.getByLabel(/password/i).fill(TEST_PASSWORD);
    await page.getByLabel(/organization/i).fill(TEST_ORG);
    await page.getByRole("button", { name: /sign up|create account/i }).click();

    // Land on the dashboard. Using URL assertion rather than text so we
    // don't depend on copy.
    await expect(page).toHaveURL(/\/(dashboard|documents)/, { timeout: 15_000 });

    // ---- Upload a document ----------------------------------------------
    await page.getByRole("button", { name: /upload|add document/i }).first().click();
    const fileInput = page.locator('input[type="file"]').first();
    const buf = Buffer.from(
      "MongoRAG e2e fixture. The quick brown fox jumps over the lazy dog.\n",
    );
    await fileInput.setInputFiles({
      name: "e2e-fixture.txt",
      mimeType: "text/plain",
      buffer: buf,
    });
    // Some upload dialogs auto-submit; others have a confirm button.
    const confirm = page.getByRole("button", { name: /upload|confirm/i });
    if (await confirm.isVisible().catch(() => false)) {
      await confirm.click();
    }

    // The document row should appear with status "ready" or "processing".
    await expect(page.getByText(/e2e-fixture\.txt/i)).toBeVisible({ timeout: 30_000 });

    // ---- Ask a question --------------------------------------------------
    // The chat panel is reachable from a "Chat" / "Test" tab.
    const chatLink = page.getByRole("link", { name: /chat|test/i }).first();
    if (await chatLink.isVisible().catch(() => false)) {
      await chatLink.click();
    }

    const input = page.getByRole("textbox", { name: /message|question|ask/i }).first();
    await input.fill("What does the fox do?");
    await page.keyboard.press("Enter");

    // We assert *some* answer renders within a generous timeout; we do not
    // pin to specific copy because LLM output is non-deterministic.
    await expect(page.locator("[data-role='assistant'], [data-message-role='assistant']").first()).toBeVisible({ timeout: 60_000 });
  });
});
