import { Link, Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/Brand";
import { NotificationBell } from "../components/NotificationBell";
import { displayName } from "../lib/format";
import { endGuest } from "./guest";

/** Buyer area shell ("Organic" design): BookingBot brand, "Tìm nhà" = the AI chat, plus the buyer's viewings. */
export function BuyerLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const buyer = user?.role === "CUSTOMER" ? user : null;
  const onChat = location.pathname === "/buyer/chat";
  const onActivity = location.pathname === "/buyer/activity";

  const pill = (active: boolean) =>
    `whitespace-nowrap rounded-full px-2.5 py-2 text-sm sm:px-4 font-semibold transition ${
      active ? "bg-sand text-ink" : "text-ink/80 hover:bg-sand/60 hover:text-ink"
    }`;

  return (
    <div className="theme-organic flex min-h-dvh flex-col bg-canvas text-ink">
      <header className="sticky top-0 z-20 bg-canvas/95 backdrop-blur">
        {/* Tighter on small phones (360 px) so the sign-out button stays on screen */}
        <div className="mx-auto flex h-[4.5rem] w-full max-w-[96rem] items-center gap-2 px-3 sm:gap-3 sm:px-4 md:gap-6 md:px-6">
          {/* Back to the start: choose to view homes or to sell one */}
          <Link to="/" title="Chọn vai trò">
            <BrandLogo compact />
          </Link>

          <nav className="flex items-center gap-1" aria-label="Người mua">
            {/* "Tìm nhà" always goes back to the conversation with the assistant */}
            <Link to="/buyer/chat?home=1" className={pill(onChat)} aria-current={onChat ? "page" : undefined}>
              Tìm nhà
            </Link>
            {/* Viewings and the owners' answers: kept even when a new chat starts. Signed-in buyers only:
                for a guest it would just lead to "Đăng nhập" */}
            {buyer && (
              <Link to="/buyer/activity" className={pill(onActivity)} aria-current={onActivity ? "page" : undefined}>
                Hoạt động
              </Link>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2 md:gap-3">
            {buyer ? (
              <>
                {/* Booking updates + what the assistant found while the buyer was away */}
                <NotificationBell />
                <span className="hidden max-w-40 truncate text-sm font-medium lg:inline">{displayName(buyer.full_name)}</span>
                <button
                  type="button"
                  className="whitespace-nowrap rounded-full border border-ink/15 px-2.5 py-2 text-sm font-semibold hover:bg-sand sm:px-4"
                  onClick={() => {
                    logout();
                    endGuest();
                    navigate("/buyer");
                  }}
                  aria-label="Đăng xuất"
                >
                  {/* Phones: an exit icon, so the header fits */}
                  <svg viewBox="0 0 24 24" className="size-4 sm:hidden" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="hidden sm:inline">Đăng xuất</span>
                </button>
              </>
            ) : (
              <Link to="/buyer/login" className="whitespace-nowrap rounded-full border border-ink/15 px-4 py-2 text-sm font-semibold hover:bg-sand">
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
