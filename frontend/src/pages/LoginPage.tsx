import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import type { User } from "../api/types";
import { homePathFor, useAuth } from "../auth/AuthContext";
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
          title: "Xác thực sổ đỏ một lần",
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
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<{ debug_code?: string | null } | null>(null);
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
      else setError(err);
    } finally {
      setBusy(false);
    }
  }

  const send = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      setSent(
        await requestOtp(
          target.trim(),
          intent === "signup" ? { role, purpose: "signup" } : {},
        ),
      );
      setCode("");
    });
  };

  const verify = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      onDone(
        await verifyOtp({
          target: target.trim(),
          code: code.trim(),
          // The role only matters when an account is created; signing in works for the account the phone has
          role: needsSignup ? role : null,
          full_name: needsSignup ? fullName.trim() : null,
        }),
      );
    });
  };

  if (!sent) {
    return (
      <form onSubmit={send} className="space-y-4">
        <Steps step={1} />
        {error !== null && <ErrorBox error={error} />}
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
            pattern="0\d{9,10}"
            title="Số điện thoại Việt Nam, bắt đầu bằng 0 (10-11 số)"
            required
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
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
      <p className="text-sm text-muted">
        Đã gửi mã tới <strong className="text-ink">{target}</strong>.{" "}
        <button
          type="button"
          className="font-semibold text-brand-700 hover:underline"
          onClick={() => setSent(null)}
        >
          Đổi số
        </button>
      </p>
      {sent.debug_code && (
        <div className="flex items-center gap-3 rounded-2xl border border-dashed border-brand-200 bg-brand-50 px-4 py-3">
          <div className="min-w-0 flex-1 text-sm">
            <p className="text-muted">
              Thử nghiệm (chưa có SMS/Zalo) · mã của bạn
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
