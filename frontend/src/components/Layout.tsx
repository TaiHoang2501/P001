import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ROLE } from "../lib/format";
import { NotificationBell } from "./NotificationBell";

type NavItem = { to: string; label: string; end?: boolean };

const NAV: Record<Role | "GUEST", NavItem[]> = {
  GUEST: [],
  CUSTOMER: [
    { to: "/", label: "Trợ lý AI", end: true },
    { to: "/bookings", label: "Lịch xem của tôi" },
  ],
  OWNER: [
    { to: "/owner", label: "Căn của tôi", end: true },
    { to: "/owner/bookings", label: "Yêu cầu xem nhà" },
  ],
  INVESTOR_OPERATOR: [
    { to: "/operator", label: "Duyệt tin", end: true },
    { to: "/operator/sellers", label: "Xác thực chủ căn" },
    { to: "/operator/escalations", label: "Ngoại lệ" },
    { to: "/operator/bookings", label: "Giám sát lịch xem" },
  ],
};

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const items = NAV[user?.role ?? "GUEST"];

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "text-muted hover:text-ink"}`;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold text-brand-700">
            <span className="grid size-7 place-items-center rounded-lg bg-brand-600 text-xs text-white">BB</span>
            BookingBot
          </Link>

          <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Chính">
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} className={linkClass}>
                {i.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto hidden items-center gap-3 md:flex">
            {user ? (
              <>
                <NotificationBell />
                <span className="text-right text-xs leading-tight">
                  <span className="block font-medium text-ink">{user.full_name}</span>
                  <span className="text-muted">{ROLE[user.role]}</span>
                </span>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                >
                  Đăng xuất
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary btn-sm">
                  Đăng nhập
                </Link>
                <Link to="/register" className="btn-primary btn-sm">
                  Đăng ký
                </Link>
              </>
            )}
          </div>

          {user && (
            <div className="ml-auto md:hidden">
              <NotificationBell />
            </div>
          )}
          <button
            type="button"
            className={`btn-secondary btn-sm md:hidden ${user ? "" : "ml-auto"}`}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            Menu
          </button>
        </div>

        {open && (
          <nav id="mobile-nav" className="flex flex-col gap-1 border-t border-line px-4 py-3 md:hidden" aria-label="Chính">
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} className={linkClass} onClick={() => setOpen(false)}>
                {i.label}
              </NavLink>
            ))}
            <div className="mt-2 flex gap-2 border-t border-line pt-3">
              {user ? (
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => {
                    logout();
                    setOpen(false);
                    navigate("/");
                  }}
                >
                  Đăng xuất ({user.full_name})
                </button>
              ) : (
                <>
                  <Link to="/login" className="btn-secondary btn-sm" onClick={() => setOpen(false)}>
                    Đăng nhập
                  </Link>
                  <Link to="/register" className="btn-primary btn-sm" onClick={() => setOpen(false)}>
                    Đăng ký
                  </Link>
                </>
              )}
            </div>
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-line py-4 text-center text-xs text-muted">
        BookingBot · Chỉ BĐS Vinhomes đã xác thực · Không thanh toán/đặt cọc trực tuyến
      </footer>
    </div>
  );
}
