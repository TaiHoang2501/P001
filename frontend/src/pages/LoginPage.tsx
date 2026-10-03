import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import type { User } from "../api/types";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { ErrorBox, Notice } from "../components/ui";

type Mode = "otp" | "password";

/** Who is signing in: buyers use the buyer area, sellers/operators use BookingBot. Decides the role of new OTP accounts. */
export type Audience = "buyer" | "seller";

export function LoginPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;

  if (user) return <Navigate to={from ?? homePathFor(user)} replace />;

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="page-title mb-6">Đăng nhập</h1>
      <LoginPanel audience="seller" onDone={(u) => navigate(from ?? homePathFor(u), { replace: true })} />
    </div>
  );
}

/** OTP / password tabs, shared by BookingBot and the buyer area. */
export function LoginPanel({
  audience,
  onDone,
  otpOnly = false,
}: {
  audience: Audience;
  onDone: (u: User) => void;
  /** Just the phone + OTP form (sign-up prompts inside other flows) */
  otpOnly?: boolean;
}) {
  const [mode, setMode] = useState<Mode>("otp");

  if (otpOnly) return <OtpForm audience={audience} onDone={onDone} />;
  return (
    <>
      <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg border border-line bg-white p-1" role="tablist">
        {(
          [
            ["otp", audience === "seller" ? "Người bán (SĐT + OTP)" : "Mã OTP"],
            ["password", audience === "seller" ? "Quản trị viên" : "Mật khẩu"],
          ] as const
        ).map(([m, label]) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => setMode(m)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${mode === m ? "bg-brand-600 text-white" : "text-muted hover:text-ink"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "otp" ? <OtpForm audience={audience} onDone={onDone} /> : <PasswordForm audience={audience} onDone={onDone} />}
    </>
  );
}

function PasswordForm({ audience, onDone }: { audience: Audience; onDone: (u: User) => void }) {
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
    <form onSubmit={onSubmit} className="card space-y-4 p-6">
      {error !== null && <ErrorBox error={error} />}
      <div>
        <label htmlFor="identifier" className="label">
          {audience === "seller" ? "Email quản trị" : "Số điện thoại hoặc email"}
        </label>
        <input id="identifier" className="input" autoComplete="username" required value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
      </div>
      <div>
        <label htmlFor="password" className="label">
          Mật khẩu
        </label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <button type="submit" className="btn-primary w-full" disabled={busy}>
        {busy ? "Đang đăng nhập..." : "Đăng nhập"}
      </button>
      {audience === "seller" && (
        <p className="text-center text-xs text-muted">
          Dành cho Chủ đầu tư/Ban quản trị. Người bán nhà đăng nhập bằng số điện thoại và mã OTP.
        </p>
      )}
    </form>
  );
}

/** Buyer: phone + OTP; Seller: phone/email + OTP (spec §4.17). First use of a phone signs up with the audience's role. */
function OtpForm({ audience, onDone }: { audience: Audience; onDone: (u: User) => void }) {
  const { requestOtp, verifyOtp } = useAuth();
  const [target, setTarget] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<{ debug_code?: string | null; account_exists?: boolean } | null>(null);
  const [needsSignup, setNeedsSignup] = useState(false);
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
      if (err instanceof ApiError && err.code === "ACCOUNT_NOT_FOUND") setNeedsSignup(true);
      else setError(err);
    } finally {
      setBusy(false);
    }
  }

  const send = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      setSent(await requestOtp(target.trim(), role));
      setCode("");
    });
  };

  const verify = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      onDone(
        await verifyOtp({ target: target.trim(), code: code.trim(), role, full_name: needsSignup ? fullName.trim() : null }),
      );
    });
  };

  if (!sent) {
    return (
      <form onSubmit={send} className="card space-y-4 p-6">
        {error !== null && <ErrorBox error={error} />}
        <div>
          <label htmlFor="otp-target" className="label">
            Số điện thoại
          </label>
          <input
            id="otp-target"
            className="input"
            inputMode="tel"
            autoComplete="tel"
            placeholder="0901234567"
            pattern="0\d{9,10}"
            title="Số điện thoại Việt Nam, bắt đầu bằng 0 (10-11 số)"
            required
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Đang gửi mã..." : "Gửi mã đăng nhập"}
        </button>
        <p className="text-center text-xs text-muted">Lần đầu dùng số điện thoại, bạn sẽ được tạo tài khoản ngay sau khi nhập mã.</p>
      </form>
    );
  }

  return (
    <form onSubmit={verify} className="card space-y-4 p-6">
      {error !== null && <ErrorBox error={error} />}
      <p className="text-sm">
        Đã gửi mã tới <strong>{target}</strong>.{" "}
        <button type="button" className="text-brand-700 hover:underline" onClick={() => setSent(null)}>
          Đổi
        </button>
      </p>
      {sent.account_exists && (
        <Notice>
          Số điện thoại này đã tồn tại trên hệ thống. Nhập mã OTP để đăng nhập vào tài khoản của bạn
          {audience === "buyer" ? " — yêu cầu xem nhà sẽ được gửi bằng tài khoản này." : "."}
        </Notice>
      )}
      {sent.debug_code && (
        <Notice>
          Môi trường thử nghiệm (chưa có nhà cung cấp SMS/Zalo): mã của bạn là <strong className="font-mono">{sent.debug_code}</strong>
        </Notice>
      )}
      <div>
        <label htmlFor="otp-code" className="label">
          Mã 6 số
        </label>
        <input
          id="otp-code"
          className="input font-mono tracking-widest"
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
          <Notice>
            {audience === "buyer" ? "Số điện thoại này chưa có tài khoản" : "Số điện thoại này chưa có tài khoản người bán"} — nhập họ tên để
            tạo tài khoản mới.
          </Notice>
          <div>
            <label htmlFor="otp-name" className="label">
              Họ và tên
            </label>
            <input id="otp-name" className="input" required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
        </>
      )}
      <button type="submit" className="btn-primary w-full" disabled={busy || code.length !== 6}>
        {busy ? "Đang xác thực..." : needsSignup ? "Tạo tài khoản & đăng nhập" : "Đăng nhập"}
      </button>
    </form>
  );
}
