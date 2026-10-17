import { expect, type Page } from "@playwright/test";

/** Demo accounts (src/config.py DEMO_PHONES): no SMS, the code 123456 is filled in on screen. */
export const DEMO = {
  buyer: "0901111222",
  seller: "0912345678",
  operatorEmail: process.env.E2E_OPERATOR_EMAIL ?? "operator@vinhomes.vn",
  operatorPassword: process.env.E2E_OPERATOR_PASSWORD ?? "Password123!",
  otp: "123456",
};

/** Phone + OTP sign-in on the buyer (/buyer/login) or seller (/login) page. */
export async function signInWithPhone(page: Page, path: "/buyer/login" | "/login", phone: string) {
  await page.goto(path);
  await page.getByLabel("Số điện thoại").fill(phone);
  await page.getByRole("button", { name: "Gửi mã đăng nhập" }).click();
  const code = page.getByLabel("Mã 6 số");
  // A demo phone gets its fixed code filled in; fill it anyway in case the server shows it without prefilling
  await expect(code).toBeVisible();
  if ((await code.inputValue()) !== DEMO.otp) await code.fill(DEMO.otp);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
}
