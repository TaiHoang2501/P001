import { Link, Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "../../auth/AuthContext";
import { NotificationBell } from "../../components/NotificationBell";
import { needsAnswer, useOwnerBookings } from "./ownerData";

/** Seller area shell ("Dành cho chủ căn" design): sand + terracotta, three places in the top bar. */
export function SellerShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const path = useLocation().pathname;
  const waiting = useOwnerBookings().data?.filter((b) => needsAnswer(b)).length ?? 0;
  // "Hoàng Thị Lan" -> "HL": family name and given name
  const words = (user?.full_name ?? "").split(/\s+/).filter(Boolean);
  const initials = (words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0]?.[0] ?? "")).toUpperCase();

  const tabs = [
    { to: "/owner/bookings", label: "Yêu cầu xem", active: path.startsWith("/owner/bookings"), badge: waiting },
    // Adding a listing and changing its viewing slots belong to "Căn của tôi"
    {
      to: "/owner",
      label: "Căn của tôi",
      active: path === "/owner" || path.startsWith("/owner/properties"),
      badge: 0,
    },
    { to: "/owner/verify", label: "Sổ đỏ", active: path.startsWith("/owner/verify"), badge: 0 },
  ];

  return (
    <div className="theme-seller flex min-h-dvh flex-col bg-canvas text-ink">
      <header className="sticky top-0 z-20 bg-canvas/95 backdrop-blur">
        <div className="mx-auto flex h-[4.5rem] w-full max-w-[96rem] items-center gap-3 px-4 md:gap-6 md:px-6">
          <Link to="/owner/bookings" className="flex items-center gap-2.5">
            <span className="grid size-10 place-items-center rounded-full bg-brand-600 font-display text-lg font-bold text-canvas">
              B
            </span>
            <span className="leading-tight">
              <span className="block font-display text-lg font-bold">BookingBot</span>
              <span className="hidden text-xs font-semibold text-muted sm:block">Dành cho chủ căn</span>
            </span>
          </Link>

          <nav className="flex items-center gap-1 overflow-x-auto" aria-label="Người bán">
            {tabs.map((t) => (
              <Link
                key={t.to}
                to={t.to}
                aria-current={t.active ? "page" : undefined}
                className={`flex items-center gap-2 whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${
                  t.active ? "bg-sand text-ink" : "text-ink/80 hover:bg-sand/60 hover:text-ink"
                }`}
              >
                {t.label}
                {t.badge > 0 && (
                  <span
                    className="grid min-w-5 place-items-center rounded-full bg-brand-600 px-1.5 text-[11px] leading-5 text-canvas"
                    aria-label={`${t.badge} yêu cầu chờ bạn`}
                  >
                    {t.badge}
                  </span>
                )}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <NotificationBell />
            <span className="grid size-10 place-items-center rounded-full bg-leaf font-display text-sm font-bold text-leaf-ink" aria-hidden="true">
              {initials}
            </span>
            <span className="hidden leading-tight md:block">
              <span className="block text-sm font-semibold">{user?.full_name}</span>
              <button
                type="button"
                className="text-xs text-muted hover:text-ink hover:underline"
                onClick={() => {
                  logout();
                  navigate("/");
                }}
              >
                Đăng xuất
              </button>
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[96rem] flex-1 px-4 pb-8 pt-2 md:px-6">
        <Outlet />
      </main>
    </div>
  );
}
