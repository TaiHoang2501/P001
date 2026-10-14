import type { Auth, RecaptchaVerifier } from "firebase/auth";

import type { components } from "../api/schema";

/**
 * Firebase Phone Auth (backend OTP_PROVIDER=firebase): Firebase makes the code, sends it by SMS and checks it;
 * the backend then verifies the Firebase ID token. Firebase is loaded only when the backend asks for it, and its
 * own sign-in is never kept: we only need the ID token once, our JWT is the session.
 */
export type FirebaseWebConfig = components["schemas"]["FirebaseWebConfig"];

export interface PhoneChallenge {
  /** Check the SMS code with Firebase; resolves with the ID token to send to the backend */
  confirm: (code: string) => Promise<string>;
}

let auth: Auth | null = null;
let verifier: { widget: RecaptchaVerifier; box: HTMLElement } | null = null;

async function getFirebaseAuth(config: FirebaseWebConfig): Promise<Auth> {
  if (auth) return auth;
  const [{ initializeApp }, { initializeAuth, inMemoryPersistence }] = await Promise.all([
    import("firebase/app"),
    import("firebase/auth"),
  ]);
  const app = initializeApp(
    { apiKey: config.api_key, authDomain: config.auth_domain, projectId: config.project_id },
    "bookingbot-otp",
  );
  auth = initializeAuth(app, { persistence: inMemoryPersistence });
  // The SMS and the reCAPTCHA in Vietnamese
  auth.languageCode = "vi";
  return auth;
}

/** "0912345678" -> "+84912345678" */
function e164(phone: string): string {
  return "+84" + phone.replace(/\D/g, "").replace(/^0/, "");
}

/** Have Firebase send a sign-in code by SMS to `phone` (Vietnamese mobile, "09xxxxxxxx"). */
export async function sendFirebaseCode(config: FirebaseWebConfig, phone: string): Promise<PhoneChallenge> {
  try {
    const firebaseAuth = await getFirebaseAuth(config);
    const { RecaptchaVerifier, signInWithPhoneNumber, signOut } = await import("firebase/auth");
    // A fresh invisible reCAPTCHA per send: a cleared one cannot render into the same element again
    if (verifier) {
      verifier.widget.clear();
      verifier.box.remove();
    }
    const box = document.createElement("div");
    document.body.appendChild(box);
    verifier = { widget: new RecaptchaVerifier(firebaseAuth, box, { size: "invisible" }), box };
    const confirmation = await signInWithPhoneNumber(firebaseAuth, e164(phone), verifier.widget);
    return {
      confirm: async (code) => {
        try {
          const credential = await confirmation.confirm(code);
          const token = await credential.user.getIdToken();
          await signOut(firebaseAuth);
          return token;
        } catch (err) {
          throw friendly(err);
        }
      },
    };
  } catch (err) {
    throw friendly(err);
  }
}

const MESSAGES: Record<string, string> = {
  "auth/invalid-verification-code": "Mã không đúng. Vui lòng kiểm tra tin nhắn và nhập lại.",
  "auth/code-expired": "Mã đã hết hạn. Bấm “Gửi lại mã” để nhận mã mới.",
  "auth/session-expired": "Mã đã hết hạn. Bấm “Gửi lại mã” để nhận mã mới.",
  "auth/missing-verification-code": "Vui lòng nhập mã 6 số.",
  "auth/invalid-phone-number": "Số điện thoại không hợp lệ.",
  "auth/too-many-requests": "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau ít phút.",
  "auth/quota-exceeded": "Hệ thống tạm hết lượt gửi tin nhắn. Vui lòng thử lại sau.",
  "auth/captcha-check-failed": "Không xác minh được bạn không phải robot. Vui lòng tải lại trang và thử lại.",
  "auth/network-request-failed": "Không kết nối được dịch vụ gửi mã. Kiểm tra mạng và thử lại.",
  "auth/operation-not-allowed": "Đăng nhập bằng số điện thoại đang tạm tắt. Vui lòng thử lại sau.",
  "auth/unauthorized-domain": "Trang này chưa được phép gửi mã đăng nhập. Vui lòng báo quản trị viên.",
};

function friendly(err: unknown): Error {
  const code = (err as { code?: unknown } | null)?.code;
  if (typeof code === "string") return new Error(MESSAGES[code] ?? "Không gửi hoặc kiểm tra được mã. Vui lòng thử lại.");
  return err instanceof Error ? err : new Error(String(err));
}
