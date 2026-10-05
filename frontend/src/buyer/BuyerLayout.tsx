import { Link, Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { NotificationBell } from "../components/NotificationBell";
import { endGuest } from "./guest";

/** Buyer area shell ("Organic" design): BookingBot brand, "Tìm nhà" = the AI chat, plus the buyer's viewings. */
export function BuyerLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const buyer = user?.role === "CUSTOMER" ? user : null;
  const onChat = location.pathname === "/buyer/chat";
  const onBookings = onChat && new URLSearchParams(location.search).has("bookings");

  const pill = (active: boolean) =>
    `whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${
      active ? "bg-sand text-ink" : "text-ink/80 hover:bg-sand/60 hover:text-ink"
    }`;

  return (
    <div className="theme-organic flex min-h-dvh flex-col bg-canvas text-ink">
      <header className="sticky top-0 z-20 bg-canvas/95 backdrop-blur">
        <div className="mx-auto flex h-[4.5rem] w-full max-w-[96rem] items-center gap-3 px-4 md:gap-6 md:px-6">
          {/* Back to the start: choose to view homes or to sell one */}
          <Link to="/" className="flex items-center gap-2.5" title="Chọn vai trò">
            <span className="grid size-10 place-items-center rounded-full bg-brand-600 font-display text-lg font-bold text-canvas">
              B
            </span>
            <span className="leading-tight">
              <span className="block font-display text-lg font-bold">BookingBot</span>
              <span className="hidden text-xs text-muted sm:block">dành cho căn Vinhomes</span>
            </span>
          </Link>

          <nav className="flex items-center gap-1" aria-label="Người mua">
            {/* "Tìm nhà" always goes back to the conversation with the assistant */}
            <Link to="/buyer/chat?home=1" className={pill(onChat && !onBookings)} aria-current={onChat && !onBookings ? "page" : undefined}>
              Tìm nhà
            </Link>
            <Link to="/buyer/chat?bookings=1" className={`${pill(onBookings)} hidden sm:inline-block`}>
              Lịch xem của tôi
            </Link>
          </nav>

          <div className="ml-auto flex items-center gap-2 md:gap-3">
            <Link to="/login" className="hidden text-sm text-muted hover:text-ink md:inline">
              Chủ căn?
            </Link>
            {buyer ? (
              <>
                {/* Booking updates + what the assistant found while the buyer was away */}
                <NotificationBell />
                <span className="hidden max-w-40 truncate text-sm font-medium lg:inline">{buyer.full_name}</span>
                <button
                  type="button"
                  className="rounded-full border border-ink/15 px-4 py-2 text-sm font-semibold hover:bg-sand"
                  onClick={() => {
                    logout();
                    endGuest();
                    navigate("/buyer");
                  }}
                >
                  Đăng xuất
                </button>
              </>
            ) : (
              <Link to="/buyer/login" className="rounded-full border border-ink/15 px-4 py-2 text-sm font-semibold hover:bg-sand">
                Đăng nhập
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[96rem] flex-1 px-4 pb-6 pt-2 md:px-6">
        <Outlet />
      </main>
    </div>
  );
}
