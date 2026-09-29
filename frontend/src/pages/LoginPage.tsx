import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import type { User } from "../api/types";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { ErrorBox, Notice } from "../components/ui";

type Mode = "otp" | "password";

export function LoginPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [mode, setMode] = useState<Mode>("otp");

  if (user) return <Navigate to={from ?? homePathFor(user)} replace />;
  const done = (u: User) => navigate(from ?? homePathFor(u), { replace: true });

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="page-title mb-6">Đăng nhập</h1>
      <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg border border-line bg-white p-1" role="tablist">
        {(
          [
            ["otp", "Mã OTP"],
            ["password", "Mật khẩu"],
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
      {mode === "otp" ? <OtpForm onDone={done} /> : <PasswordForm onDone={done} />}
    </div>
  );
}

function PasswordForm({ onDone }: { onDone: (u: User) => void }) {
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
          Số điện thoại hoặc email
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
      <p className="text-center text-xs text-muted">Chủ đầu tư/Ban quản trị đăng nhập bằng email và mật khẩu.</p>
      <p className="text-center text-sm text-muted">
        Chưa có tài khoản?{" "}
        <Link to="/register" className="font-medium text-brand-700 hover:underline">
          Đăng ký
        </Link>
      </p>
    </form>
  );
}

/** Buyer: phone + OTP; Seller: phone/email + OTP (spec §4.17). First use of a phone signs up. */
function OtpForm({ onDone }: { onDone: (u: User) => void }) {
  const { requestOtp, verifyOtp } = useAuth();
  const [target, setTarget] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<{ debug_code?: string | null } | null>(null);
  const [needsSignup, setNeedsSignup] = useState(false);
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<"CUSTOMER" | "OWNER">("CUSTOMER");
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
      setSent(await requestOtp(target.trim()));
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
            Số điện thoại (hoặc email chủ căn)
          </label>
          <input
            id="otp-target"
            className="input"
            inputMode="tel"
            autoComplete="tel"
            placeholder="0901234567"
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
          <Notice>Số điện thoại này chưa có tài khoản — nhập thông tin để tạo tài khoản mới.</Notice>
          <div>
            <label htmlFor="otp-name" className="label">
              Họ và tên
            </label>
            <input id="otp-name" className="input" required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <fieldset>
            <legend className="label">Bạn là</legend>
            <div className="grid grid-cols-2 gap-2">
              {(
                [
                  ["CUSTOMER", "Người mua"],
                  ["OWNER", "Chủ căn muốn bán"],
                ] as const
              ).map(([value, label]) => (
                <label
                  key={value}
                  className={`cursor-pointer rounded-lg border px-3 py-2 text-center text-sm ${role === value ? "border-brand-600 bg-brand-50 font-medium" : "border-line"}`}
                >
                  <input type="radio" name="role" className="sr-only" checked={role === value} onChange={() => setRole(value)} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        </>
      )}
      <button type="submit" className="btn-primary w-full" disabled={busy || code.length !== 6}>
        {busy ? "Đang xác thực..." : needsSignup ? "Tạo tài khoản & đăng nhập" : "Đăng nhập"}
      </button>
    </form>
  );
}
