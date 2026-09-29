import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";

import { homePathFor, useAuth } from "../auth/AuthContext";
import { ErrorBox } from "../components/ui";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", phone: "", email: "", password: "", role: "CUSTOMER" as "CUSTOMER" | "OWNER" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePathFor(user)} replace />;

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await register({ ...form, email: form.email.trim() || null });
      navigate(homePathFor(u), { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="page-title mb-6">Tạo tài khoản</h1>
      <form onSubmit={onSubmit} className="card space-y-4 p-6">
        {error !== null && <ErrorBox error={error} />}

        <fieldset>
          <legend className="label">Bạn là</legend>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["CUSTOMER", "Người mua", "Tìm căn & đặt lịch xem"],
                ["OWNER", "Chủ căn", "Đăng bán & xác nhận lịch xem"],
              ] as const
            ).map(([value, title, hint]) => (
              <label
                key={value}
                className={`cursor-pointer rounded-lg border p-3 text-sm ${form.role === value ? "border-brand-500 bg-brand-50" : "border-line"}`}
              >
                <input type="radio" name="role" value={value} checked={form.role === value} onChange={set("role")} className="sr-only" />
                <span className="block font-medium">{title}</span>
                <span className="text-xs text-muted">{hint}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label htmlFor="full_name" className="label">
            Họ tên
          </label>
          <input id="full_name" className="input" required minLength={2} autoComplete="name" value={form.full_name} onChange={set("full_name")} />
        </div>
        <div>
          <label htmlFor="phone" className="label">
            Số điện thoại
          </label>
          <input
            id="phone"
            className="input"
            required
            inputMode="tel"
            pattern="0\d{9,10}"
            title="Số điện thoại Việt Nam, bắt đầu bằng 0 (10-11 số)"
            autoComplete="tel"
            placeholder="0901234567"
            value={form.phone}
            onChange={set("phone")}
          />
        </div>
        <div>
          <label htmlFor="email" className="label">
            Email (không bắt buộc)
          </label>
          <input id="email" type="email" className="input" autoComplete="email" value={form.email} onChange={set("email")} />
        </div>
        <div>
          <label htmlFor="password" className="label">
            Mật khẩu (tối thiểu 8 ký tự)
          </label>
          <input
            id="password"
            type="password"
            className="input"
            required
            minLength={8}
            autoComplete="new-password"
            value={form.password}
            onChange={set("password")}
          />
        </div>
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Đang tạo..." : "Đăng ký"}
        </button>
        <p className="text-center text-sm text-muted">
          Đã có tài khoản?{" "}
          <Link to="/login" className="font-medium text-brand-700 hover:underline">
            Đăng nhập
          </Link>
        </p>
      </form>
    </div>
  );
}
