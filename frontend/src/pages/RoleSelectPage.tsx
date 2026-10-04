import type { ReactNode } from "react";
import { useNavigate } from "react-router";

import { homePathFor, useAuth } from "../auth/AuthContext";
import { ArrowRightIcon, PriceTagIcon, SearchHomeIcon, UserIcon } from "../buyer/icons";

/**
 * Entry point: the visitor says whether they want to view homes (buyer area with the AI agent)
 * or sell one (BookingBot seller portal, which also hosts the investor/operator console).
 */
export function RoleSelectPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function viewHomes() {
    // A seller/operator session would be bounced by the buyer area: sign out first
    if (user && user.role !== "CUSTOMER") logout();
    navigate(user?.role === "CUSTOMER" ? "/buyer/chat" : "/buyer/start");
  }

  function sellHome() {
    if (user?.role === "CUSTOMER") logout();
    navigate(user && user.role !== "CUSTOMER" ? homePathFor(user) : "/login");
  }

  return (
    <div className="theme-buyer relative grid min-h-dvh place-items-center overflow-hidden bg-slate-200 px-4 py-10">
      {/* Soft backdrop standing in for the page behind the dialog */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute -left-24 top-10 size-96 rounded-full bg-brand-200/60 blur-3xl" />
        <div className="absolute -right-16 bottom-0 size-[28rem] rounded-full bg-slate-300 blur-3xl" />
      </div>

      <main
        className="relative w-full max-w-[56rem] rounded-[2rem] bg-slate-50 p-6 shadow-2xl shadow-slate-900/10 sm:p-11"
        aria-labelledby="role-title"
      >
        <span className="grid size-14 place-items-center rounded-2xl bg-brand-600 text-white">
          <UserIcon className="size-7" />
        </span>
        <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-brand-600">Trước khi bắt đầu</p>
        <h1 id="role-title" className="mt-2 text-4xl font-bold tracking-tight text-ink sm:text-[3.6rem] sm:leading-tight">
          Bạn muốn làm gì hôm nay?
        </h1>

        <div className="mt-7 space-y-3.5">
          <Choice
            icon={<SearchHomeIcon className="size-6" />}
            title="Tôi là người xem nhà"
            hint="Trò chuyện với Trợ lý AI để tìm căn phù hợp và đặt lịch xem"
            onClick={viewHomes}
          />
          <Choice
            icon={<PriceTagIcon className="size-6" />}
            title="Tôi là người bán nhà"
            hint="Đăng bán căn, quản lý lịch xem và yêu cầu từ khách"
            onClick={sellHome}
          />
        </div>

        <p className="mt-7 text-sm text-muted">Bạn có thể quay lại màn hình này để đổi lựa chọn bất cứ lúc nào.</p>
      </main>
    </div>
  );
}

function Choice({ icon, title, hint, onClick }: { icon: ReactNode; title: string; hint: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-5 rounded-2xl border border-line bg-white px-6 py-5 text-left transition hover:border-brand-500 hover:shadow-md hover:shadow-brand-600/5"
    >
      <span className="shrink-0 text-ink group-hover:text-brand-600">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-lg font-semibold text-ink">{title}</span>
        <span className="mt-0.5 block text-sm text-muted">{hint}</span>
      </span>
      <ArrowRightIcon className="size-5 shrink-0 text-ink transition-transform group-hover:translate-x-1 group-hover:text-brand-600" />
    </button>
  );
}
