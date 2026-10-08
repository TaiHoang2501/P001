import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { NotificationBell } from "../components/NotificationBell";
import { endGuest } from "./guest";
import { BuildingIcon } from "./icons";

// Buyers land in the AI chat; the only other place is their viewings (a card in that chat)
const NAV = [{ to: "/buyer/chat?bookings=1", label: "Lịch xem của tôi" }];

/** Buyer area shell (wireframe 1.x): blue theme, its own header, no seller/operator navigation. */
export function BuyerLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const buyer = user?.role === "CUSTOMER" ? user : null;
  // The chat page can open the home details beside it: give it more room
  const width = useLocation().pathname === "/buyer/chat" ? "max-w-[96rem]" : "max-w-6xl";

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "text-brand-600" : "text-muted hover:text-ink"}`;

  return (
    <div className="theme-buyer flex min-h-dvh flex-col bg-canvas text-ink">
      <header className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur">
        <div className={`mx-auto flex h-16 ${width} items-center gap-4 px-4`}>
          {/* Back to the start: choose to view homes or to sell one */}
          <Link
            to="/"
            className="flex items-center gap-2 font-bold text-ink"
          >
            <span className="grid size-8 place-items-center rounded-lg bg-brand-600 text-white">
              <BuildingIcon className="size-5" />
            </span>
            Vinhomes
          </Link>

          <nav
            className="hidden flex-1 items-center gap-1 sm:flex"
            aria-label="Người mua"
          >
            {NAV.map((i) => (
              <NavLink
                key={i.to}
                to={i.to}
                className={
                  i.to.includes("?")
                    ? linkClass({ isActive: false })
                    : linkClass
                }
              >
                {i.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <Link
              to="/"
              className="hidden text-xs text-muted hover:text-ink md:inline"
            >
              Đổi vai trò
            </Link>
            {buyer ? (
              <>
                {/* Booking updates + what the AI agent found while the buyer was away */}
                <NotificationBell />
                <span className="hidden max-w-40 truncate text-sm font-medium md:inline">
                  {buyer.full_name}
                </span>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
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
              <Link
                to="/buyer/login"
                className="btn btn-sm border border-brand-600 bg-white text-brand-600 hover:bg-brand-50"
              >
                Đăng nhập
              </Link>
            )}
          </div>
        </div>

        <nav
          className="flex gap-1 overflow-x-auto border-t border-line px-2 sm:hidden"
          aria-label="Người mua"
        >
          {NAV.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              className={
                i.to.includes("?") ? linkClass({ isActive: false }) : linkClass
              }
            >
              {i.label}
            </NavLink>
          ))}
          <Link
            to="/"
            className="whitespace-nowrap rounded-lg px-3 py-2 text-sm text-muted"
          >
            Đổi vai trò
          </Link>
        </nav>
      </header>

      <main className={`mx-auto w-full ${width} flex-1 px-4 py-6 md:py-8`}>
        <Outlet />
      </main>

      <footer className="border-t border-line py-4 text-center text-xs text-muted">
        Chỉ căn Vinhomes đã xác thực · Kết nối trực tiếp chủ căn · Không thanh
        toán/đặt cọc trực tuyến
      </footer>
    </div>
  );
}
