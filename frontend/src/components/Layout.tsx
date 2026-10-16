import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { api, call } from "../api/client";
import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ROLE } from "../lib/format";
import { SellerShell } from "../pages/owner/SellerShell";
import { NotificationBell } from "./NotificationBell";

type NavItem = { to: string; label: string; end?: boolean; count?: "listings" | "cases" };

const NAV: Record<Role | "GUEST", NavItem[]> = {
  GUEST: [],
  // Buyers use the separate buyer area (/buyer); BookingBot is for sellers and the investor/operator
  CUSTOMER: [],
  // Sellers have their own shell (SellerShell): its top bar holds their pages
  OWNER: [],
  INVESTOR_OPERATOR: [
    { to: "/operator", label: "Duyệt tin", end: true, count: "listings" },
    { to: "/operator/escalations", label: "Ngoại lệ", count: "cases" },
    { to: "/operator/bookings", label: "Lịch xem" },
  ],
};

/** The operator's work still to do: listings waiting for review and open cases (same queries as their pages). */
function useOperatorCounts(enabled: boolean): Record<"listings" | "cases", number | undefined> {
  const listings = useQuery({
    queryKey: ["moderation"],
    queryFn: () => call(api.GET("/api/v1/operator/properties", { params: { query: { status: "PENDING_REVIEW" } } })),
    enabled,
    refetchInterval: 60_000,
  });
  const cases = useQuery({
    queryKey: ["escalations", false],
    queryFn: () => call(api.GET("/api/v1/operator/escalations", { params: { query: {} } })),
    enabled,
    refetchInterval: 60_000,
  });
  return { listings: listings.data?.length, cases: cases.data?.length };
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const items = NAV[user?.role ?? "GUEST"];
  const path = useLocation().pathname;
  const sellerPage = user?.role === "OWNER" && path.startsWith("/owner");
  // The investor/operator console and the sellers' site share this frame but are separate places: each signs in on
  // its own page and never points to the other's sign-in
  const operatorArea = path.startsWith("/operator");
  const loginPath = operatorArea ? "/operator/login" : "/login";
  const onLoginPage = path === loginPath;
  const counts = useOperatorCounts(user?.role === "INVESTOR_OPERATOR");
  // The browser tab says which page this is, and how much is waiting there ("(4) Ngoại lệ · BookingBot")
  const current = [...items].sort((a, b) => b.to.length - a.to.length).find((i) => (i.end ? path === i.to : path.startsWith(i.to)));
  const waiting = current?.count ? counts[current.count] : undefined;
  useEffect(() => {
    if (sellerPage || !current) return;
    document.title = `${waiting ? `(${waiting}) ` : ""}${current.label} · BookingBot`;
    return () => {
      document.title = "BookingBot";
    };
  }, [sellerPage, current, waiting]);

  if (sellerPage) return <SellerShell />;

  const label = (i: NavItem) => {
    const n = i.count ? counts[i.count] : undefined;
    return (
      <>
        {i.label}
        {!!n && (
          <span className="ml-1.5 rounded-full bg-brand-600 px-1.5 py-0.5 text-[11px] font-semibold text-white">{n}</span>
        )}
      </>
    );
  };

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "text-muted hover:text-ink"}`;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          {/* The investor's console is its own place: its logo leads nowhere (the start page is for buyers / sellers) */}
          {path.startsWith("/operator") ? (
            <span className="flex select-none items-center gap-2 font-semibold text-brand-700">
              <span className="grid size-7 place-items-center rounded-lg bg-brand-600 text-xs text-white">BB</span>
              BookingBot
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">Chủ đầu tư</span>
            </span>
          ) : (
            <Link to="/" className="flex items-center gap-2 font-semibold text-brand-700">
              <span className="grid size-7 place-items-center rounded-lg bg-brand-600 text-xs text-white">BB</span>
              BookingBot
            </Link>
          )}

          <nav
            className="hidden flex-1 items-center gap-1 lg:flex"
            aria-label="Chính"
          >
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} className={linkClass}>
                {label(i)}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto hidden items-center gap-3 lg:flex">
            {user ? (
              <>
                <NotificationBell />
                <span className="text-right text-xs leading-tight">
                  <span className="block font-medium text-ink">
                    {user.full_name}
                  </span>
                  <span className="text-muted">{ROLE[user.role]}</span>
                </span>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => {
                    logout();
                    navigate(
                      user.role === "INVESTOR_OPERATOR"
                        ? "/operator/login"
                        : "/",
                    );
                  }}
                >
                  Đăng xuất
                </button>
              </>
            ) : (
              !onLoginPage && (
                <Link to={loginPath} className="btn-primary btn-sm">
                  Đăng nhập
                </Link>
              )
            )}
          </div>

          {user && (
            <div className="ml-auto lg:hidden">
              <NotificationBell />
            </div>
          )}
          <button
            type="button"
            className={`btn-secondary btn-sm lg:hidden ${user ? "" : "ml-auto"} ${!user && onLoginPage ? "hidden" : ""}`}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            Menu
          </button>
        </div>

        {open && (
          <nav
            id="mobile-nav"
            className="flex flex-col gap-1 border-t border-line px-4 py-3 lg:hidden"
            aria-label="Chính"
          >
            {items.map((i) => (
              <NavLink
                key={i.to}
                to={i.to}
                end={i.end}
                className={linkClass}
                onClick={() => setOpen(false)}
              >
                {label(i)}
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
                    navigate(
                      user.role === "INVESTOR_OPERATOR"
                        ? "/operator/login"
                        : "/",
                    );
                  }}
                >
                  Đăng xuất ({user.full_name})
                </button>
              ) : (
                !onLoginPage && (
                  <Link to={loginPath} className="btn-primary btn-sm" onClick={() => setOpen(false)}>
                    Đăng nhập
                  </Link>
                )
              )}
            </div>
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-line py-4 text-center text-xs text-muted">
        BookingBot · Chỉ BĐS Vinhomes đã xác thực · Không thanh toán/đặt cọc
        trực tuyến
      </footer>
    </div>
  );
}
