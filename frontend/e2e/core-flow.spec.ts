import { expect, test } from "@playwright/test";

import { DEMO, signInWithPhone } from "./helpers";

test.describe("public pages", () => {
  test("/privacy renders without signing in", async ({ page }) => {
    await page.goto("/privacy");
    await expect(page.getByRole("heading", { level: 1, name: "Chính sách quyền riêng tư" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Ai được xem dữ liệu/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Lưu trữ trong bao lâu/ })).toBeVisible();
  });

  test("the role chooser and the sign-in forms link to /privacy", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Chính sách quyền riêng tư" })).toBeVisible();
    await page.goto("/login");
    await page.getByRole("link", { name: "Chính sách quyền riêng tư" }).click();
    await expect(page).toHaveURL(/\/privacy$/);
  });

  test("/pass with an unknown token says the code is not valid", async ({ page }) => {
    await page.goto("/pass/not-a-real-token");
    await expect(page.getByRole("heading", { name: "Mã không hợp lệ" })).toBeVisible();
  });
});

test.describe("demo accounts", () => {
  test("buyer: phone + OTP 123456 opens the AI chat", async ({ page }) => {
    await signInWithPhone(page, "/buyer/login", DEMO.buyer);
    await expect(page).toHaveURL(/\/buyer\/chat/);
    await expect(page.getByLabel("Tin nhắn")).toBeVisible();
  });

  test("buyer: one message to the assistant gets a reply (E2E_CHAT=1)", async ({ page }) => {
    test.skip(!process.env.E2E_CHAT, "Calls the real LLM: set E2E_CHAT=1 to run");
    test.setTimeout(120_000);
    await signInWithPhone(page, "/buyer/login", DEMO.buyer);
    const input = page.getByLabel("Tin nhắn");
    await expect(input).toBeEnabled();
    await input.fill("Tôi tìm căn 2 phòng ngủ ở Vinhomes Ocean Park, ngân sách khoảng 4 tỷ");
    const reply = page.waitForResponse(
      (r) => /\/api\/v1\/chat(\/stream)?$/.test(new URL(r.url()).pathname) && r.request().method() === "POST",
      { timeout: 90_000 },
    );
    await page.getByRole("button", { name: "Gửi", exact: true }).click();
    expect((await reply).status()).toBe(200);
    // The send button comes back once the streamed reply is finished
    await input.fill("cảm ơn");
    await expect(page.getByRole("button", { name: "Gửi", exact: true })).toBeEnabled({ timeout: 90_000 });
  });

  test("seller: phone + OTP 123456 opens the viewing requests", async ({ page }) => {
    await signInWithPhone(page, "/login", DEMO.seller);
    await expect(page).toHaveURL(/\/owner/);
    await page.goto("/owner/bookings");
    await expect(page.getByRole("heading", { name: "Yêu cầu xem nhà" })).toBeVisible();
    // The lists of requests (pending / upcoming / ...), each tab with its count
    const tabs = page.getByRole("tablist", { name: "Danh sách" }).getByRole("tab");
    await expect(tabs.first()).toBeVisible();
    expect(await tabs.count()).toBeGreaterThan(1);
  });

  test("operator: email + password opens listing moderation", async ({ page }) => {
    await page.goto("/operator/login");
    await page.getByLabel("Email").fill(DEMO.operatorEmail);
    await page.getByLabel("Mật khẩu").fill(DEMO.operatorPassword);
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    await expect(page).toHaveURL(/\/operator$/);
    await expect(page.getByRole("heading", { name: "Duyệt tin đăng" })).toBeVisible();
  });
});
