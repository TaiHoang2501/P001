import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import type { User } from "../api/types";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { sendFirebaseCode, type PhoneChallenge } from "../auth/firebasePhone";
import { AuthShell, RedBookHomeArt } from "../components/AuthShell";
import { ErrorBox, Notice } from "../components/ui";

/** Who is signing in: buyers use the buyer area, sellers/operators use BookingBot. Decides the role of new OTP accounts. */
export type Audience = "buyer" | "seller";

/** Sellers only: phone + OTP. Operators have their own page (/operator/login), not linked from here. */
export function LoginPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;

  if (user) return <Navigate to={from ?? homePathFor(user)} replace />;

  return (
    <AuthShell
      tone="seller"
      eyebrow="BookingBot · Dành cho chủ căn"
      headline="Bán căn Vinhomes của bạn, gặp đúng người mua."
      art={<RedBookHomeArt />}
      points={[
        {
          title: "Xác thực sổ đỏ / sổ hồng một lần",
          text: "Đối chiếu với dữ liệu Chủ đầu tư, rồi đăng bán ngay.",
        },
        {
          title: "Trợ lý AI giới thiệu căn của bạn",
          text: "Chỉ gợi ý cho người mua có nhu cầu phù hợp.",
        },
        {
          title: "Bạn quyết định từng lịch xem",
          text: "Xác nhận hoặc từ chối trong một chạm, không qua môi giới.",
        },
      ]}
      title="Đăng nhập người bán"
      subtitle="Dùng số điện thoại, không cần mật khẩu."
    >
      <LoginPanel
        audience="seller"
        onDone={(u) => navigate(from ?? homePathFor(u), { replace: true })}
      />
    </AuthShell>
  );
}

/** Investor / operator console: email + password, on its own page. */
export function OperatorLoginPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;

  if (user) return <Navigate to={from ?? homePathFor(user)} replace />;

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="page-title">Bảng Chủ đầu tư</h1>
      <p className="mb-6 mt-1 text-sm text-muted">
        Khu vực dành cho quản trị viên.
      </p>
      <PasswordForm
        operator
        onDone={(u) => navigate(from ?? homePathFor(u), { replace: true })}
      />
    </div>
  );
}

/** Buyers and sellers sign in with phone + OTP only; passwords are just for the operator page. */
export function LoginPanel({
  audience,
  onDone,
  intent = "login",
}: {
  audience: Audience;
  onDone: (u: User) => void;
  /** "signup": a new account only, so a phone already on the system is refused */
  intent?: OtpIntent;
}) {
  return <OtpForm key={intent} audience={audience} onDone={onDone} intent={intent} />;
}

function PasswordForm({
  operator = false,
  onDone,
}: {
  operator?: boolean;
  onDone: (u: User) => void;
}) {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onDone(await login(identifier, password));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {error !== null && <ErrorBox error={error} />}
      <div>
        <label
          htmlFor="identifier"
          className="mb-1.5 block text-sm font-semibold"
        >
          {operator ? "Email" : "Số điện thoại hoặc email"}
        </label>
        <input
          id="identifier"
          className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none transition placeholder:text-muted/70 focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
          autoComplete="username"
          required
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
        />
      </div>
      <div>
        <label
          htmlFor="password"
          className="mb-1.5 block text-sm font-semibold"
        >
          Mật khẩu
        </label>
        <input
          id="password"
          type="password"
          className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none transition placeholder:text-muted/70 focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <button
        type="submit"
        className="w-full rounded-2xl bg-brand-600 px-4 py-3.5 text-base font-bold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
        disabled={busy}
      >
        {busy ? "Đang đăng nhập..." : "Đăng nhập"}
      </button>
    </form>
  );
}

/** Buyer: phone + OTP; Seller: phone/email + OTP (spec §4.17). First use of a phone signs up with the audience's role. */
export type OtpIntent = "login" | "signup";

type Sent = { provider?: "local" | "firebase"; debug_code?: string | null; demo?: boolean; expires_in?: number };

/**
 * login: a code goes to any phone; a phone with no account yet is then signed up (name asked after the code).
 * signup: creating a new account; a phone already on the system is refused before any code is sent.
 */
function OtpForm({
  audience,
  onDone,
  intent = "login",
}: {
  audience: Audience;
  onDone: (u: User) => void;
  intent?: OtpIntent;
}) {
  const { requestOtp, verifyOtp } = useAuth();
  const [target, setTarget] = useState("");
  // Shown under the phone box (not the browser's own tooltip)
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const phone = target.replace(/\s/g, "");
  // A new code can be asked for 60 s after the last one (the countdown is shown on the resend link)
  const [resendAt, setResendAt] = useState(0);
  // When the code sent last stops working (shown as a countdown)
  const [expireAt, setExpireAt] = useState(0);
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    if (Math.max(resendAt, expireAt) <= clock) return;
    const t = setTimeout(() => setClock(Date.now()), 1000);
    return () => clearTimeout(t);
  }, [resendAt, expireAt, clock]);
  const expiresIn = Math.max(0, Math.ceil((expireAt - clock) / 1000));
  // A code was just sent: start both countdowns
  const gotCode = (res: Sent) => {
    setSent(res);
    setExpireAt(Date.now() + (res.expires_in ?? 300) * 1000);
    setResendAt(Date.now() + 60_000);
    setClock(Date.now());
  };
  const resendIn = Math.max(0, Math.ceil((resendAt - clock) / 1000));
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<Sent | null>(null);
  // Firebase Phone Auth: the SMS Firebase sent, and the ID token once its code was checked (kept for the sign-up
  // details step, since a Firebase code works only once)
  const [challenge, setChallenge] = useState<PhoneChallenge | null>(null);
  const [idToken, setIdToken] = useState<string | null>(null);
  const firebase = sent?.provider === "firebase";
  const [needsSignup, setNeedsSignup] = useState(intent === "signup");
  const [fullName, setFullName] = useState("");
  const role = audience === "buyer" ? "CUSTOMER" : "OWNER";
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      if (err instanceof ApiError && err.code === "ACCOUNT_NOT_FOUND")
        setNeedsSignup(true);
      else {
        // The backend refused the Firebase token: the next try needs a new code
        if (err instanceof ApiError) setIdToken(null);
        setError(err);
      }
    } finally {
      setBusy(false);
    }
  }

  const send = (e: FormEvent) => {
    e.preventDefault();
    if (!/^0[35789]\d{8}$/.test(phone)) {
      setPhoneError("Nhập số di động 10 chữ số, bắt đầu bằng 03, 05, 07, 08 hoặc 09, ví dụ 0912 345 678.");
      return;
    }
    setPhoneError(null);
    void run(sendCode);
  };

  async function sendCode() {
    // The role is always sent, so a seller's number on the buyer page (and back) is turned away with a pointer
    const res = await requestOtp(phone, intent === "signup" ? { role, purpose: "signup" } : { role });
    // Firebase Phone Auth: the checks passed, now Firebase sends the SMS
    if (res.provider === "firebase" && res.firebase) setChallenge(await sendFirebaseCode(res.firebase, phone));
    setIdToken(null);
    gotCode(res);
    // Demo accounts get no SMS: their code is filled in, the tester only presses "Đăng nhập"
    setCode(res.demo ? (res.debug_code ?? "") : "");
  }

  const verify = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      let token: string | null = null;
      if (firebase) {
        token = idToken ?? (await challenge!.confirm(code.trim()));
        setIdToken(token);
      }
      onDone(
        await verifyOtp({
          target: phone,
          ...(token ? { firebase_id_token: token } : { code: code.trim() }),
          // The role only matters when an account is created; signing in works for the account the phone has
          role: needsSignup ? role : null,
          full_name: needsSignup ? fullName.trim() : null,
        }),
      );
    });
  };

  if (!sent) {
    return (
      <form onSubmit={send} className="space-y-4" noValidate>
        <Steps step={1} />
        {error !== null && <OtherAreaOrError error={error} intent={intent} />}
        <div>
          <label
            htmlFor="otp-target"
            className="mb-1.5 block text-sm font-semibold"
          >
            Số điện thoại
          </label>
          <input
            id="otp-target"
            className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none transition placeholder:text-muted/70 focus:border-brand-500 focus:ring-4 focus:ring-brand-100 tracking-wide"
            inputMode="tel"
            autoComplete="tel"
            placeholder="09xx xxx xxx"
            aria-invalid={phoneError !== null}
            aria-describedby={phoneError ? "otp-target-error" : undefined}
            value={target}
            // Digits only, grouped as 09xx xxx xxx while typing
            onChange={(e) => {
              setPhoneError(null);
              let digits = e.target.value.replace(/\D/g, "");
              // +84 912 345 678 -> 0912 345 678
              if (digits.startsWith("84") && digits.length >= 11) digits = "0" + digits.slice(2);
              setTarget(groupPhone(digits.slice(0, 11)));
            }}
          />
          {phoneError && (
            <p id="otp-target-error" className="mt-1.5 text-sm font-medium text-red-700">
              {phoneError}
            </p>
          )}
        </div>
        <button
          type="submit"
          className="w-full rounded-2xl bg-brand-600 px-4 py-3.5 text-base font-bold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
          disabled={busy}
        >
          {busy
            ? "Đang gửi mã..."
            : intent === "signup"
              ? "Gửi mã xác thực"
              : "Gửi mã đăng nhập"}
        </button>
        <p className="text-center text-xs text-muted">
          {intent === "signup"
            ? "Dùng số điện thoại chưa đăng ký trên hệ thống."
            : "Lần đầu dùng số điện thoại, bạn sẽ được tạo tài khoản ngay sau khi nhập mã."}
        </p>
      </form>
    );
  }

  return (
    <form onSubmit={verify} className="space-y-4">
      <Steps step={2} />
      {error !== null && <ErrorBox error={error} />}
      {/* A Firebase SMS code keeps its own expiry; Firebase says when it has run out */}
      {!firebase && !sent.demo && (
        <p className={`text-sm ${expiresIn === 0 ? "font-medium text-red-700" : "text-muted"}`}>
          {expiresIn > 0
            ? `Mã hết hạn sau ${Math.floor(expiresIn / 60)}:${String(expiresIn % 60).padStart(2, "0")}.`
            : "Mã đã hết hạn. Bấm “Gửi lại mã” để nhận mã mới."}
        </p>
      )}
      <p className="text-sm text-muted">
        {sent.demo ? "Tài khoản demo, không gửi SMS: mã đã được điền sẵn cho " : `Đã gửi mã ${firebase ? "qua tin nhắn SMS " : ""}tới `}
        <strong className="text-ink">{target}</strong>.{" "}
        <button
          type="button"
          className="font-semibold text-brand-700 hover:underline"
          onClick={() => {
            setSent(null);
            setError(null);
          }}
        >
          Đổi số
        </button>
      </p>
      {sent.debug_code && !sent.demo && (
        <div className="flex items-center gap-3 rounded-2xl border border-dashed border-brand-200 bg-brand-50 px-4 py-3">
          <div className="min-w-0 flex-1 text-sm">
            <p className="text-muted">
              Chế độ thử nghiệm (không gửi SMS) · mã của bạn
            </p>
            <strong className="font-mono text-xl tracking-[0.3em]">
              {sent.debug_code}
            </strong>
          </div>
          <button
            type="button"
            className="rounded-xl bg-white px-3 py-2 text-sm font-semibold text-brand-700 shadow-sm hover:bg-brand-100"
            onClick={() => setCode(sent.debug_code ?? "")}
          >
            Điền giúp
          </button>
        </div>
      )}
      <div>
        <label
          htmlFor="otp-code"
          className="mb-1.5 block text-sm font-semibold"
        >
          Mã 6 số
        </label>
        <input
          id="otp-code"
          placeholder="••••••"
          className="w-full rounded-2xl border border-line bg-white px-4 py-3.5 text-center font-mono text-2xl tracking-[0.6em] outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          required
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        />
      </div>
      {needsSignup && (
        <>
          {intent === "login" && (
            <Notice>
              {audience === "buyer"
                ? "Số điện thoại này chưa có tài khoản"
                : "Số điện thoại này chưa có tài khoản người bán"}{" "}
              — nhập họ tên để tạo tài khoản mới.
            </Notice>
          )}
          <div>
            <label
              htmlFor="otp-name"
              className="mb-1.5 block text-sm font-semibold"
            >
              Họ và tên
            </label>
            <input
              id="otp-name"
              className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none transition placeholder:text-muted/70 focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
              required
              minLength={2}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
        </>
      )}
      <button
        type="submit"
        className="w-full rounded-2xl bg-brand-600 px-4 py-3.5 text-base font-bold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
        disabled={busy || code.length !== 6}
      >
        {busy
          ? "Đang xác thực..."
          : needsSignup
            ? "Tạo tài khoản & đăng nhập"
            : "Đăng nhập"}
      </button>
      <p className="text-center text-sm text-muted">
        Chưa nhận được mã?{" "}
        {resendIn > 0 ? (
          <span>Gửi lại sau {resendIn} giây</span>
        ) : (
          <button
            type="button"
            className="font-semibold text-brand-700 hover:underline disabled:opacity-50"
            disabled={busy}
            onClick={() => void run(sendCode)}
          >
            Gửi lại mã
          </button>
        )}
      </p>
    </form>
  );
}

/** "1 Số điện thoại → 2 Nhập mã" */
function Steps({ step }: { step: 1 | 2 }) {
  const item = (n: 1 | 2, label: string) => (
    <span
      className={`flex items-center gap-2 ${step >= n ? "text-ink" : "text-muted"}`}
    >
      <span
        className={`grid size-6 place-items-center rounded-full text-xs font-bold ${
          step > n
            ? "bg-emerald-500 text-white"
            : step === n
              ? "bg-brand-600 text-white"
              : "bg-slate-200 text-muted"
        }`}
      >
        {step > n ? "✓" : n}
      </span>
      {label}
    </span>
  );
  return (
    <div
      className="flex items-center gap-3 text-sm font-semibold"
      aria-label={`Bước ${step} trên 2`}
    >
      {item(1, "Số điện thoại")}
      <span className="h-px flex-1 bg-line" aria-hidden="true" />
      {item(2, "Nhập mã")}
    </div>
  );
}

/** "0912345678" -> "0912 345 678" (an 11-digit number keeps its last four together). */
function groupPhone(digits: string): string {
  return [digits.slice(0, 4), digits.slice(4, 7), digits.slice(7)].filter(Boolean).join(" ");
}

/** A phone of the other kind of account (a seller's number on the buyer page, or back): say where to sign in. */
function OtherAreaOrError({ error, intent }: { error: unknown; intent: OtpIntent }) {
  const role = error instanceof ApiError && error.code === "PHONE_IN_USE" ? error.details.account_role : undefined;
  if (intent === "login" && (role === "OWNER" || role === "CUSTOMER")) {
    const seller = role === "OWNER";
    return (
      <Notice tone="warning">
        Số này là tài khoản {seller ? "người bán" : "người mua"}.{" "}
        <Link to={seller ? "/login" : "/buyer/login"} className="font-semibold underline">
          Đăng nhập ở trang {seller ? "người bán" : "người mua"}
        </Link>{" "}
        hoặc dùng số khác.
      </Notice>
    );
  }
  return <ErrorBox error={error} />;
}
