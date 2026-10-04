import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { startGuest } from "./guest";
import { ArrowRightIcon, SparkleIcon, UserIcon } from "./icons";

/**
 * Asked before the chat: new buyers talk to the agent right away and sign up only when they send a
 * viewing request; returning buyers sign in first so they see their earlier viewings.
 */
export function BuyerStartPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<IntroPhase>("in");

  // Slogan grows in (2.6s), fades out (0.7s), then the question
  useEffect(() => {
    if (phase === "done") return;
    const t = setTimeout(() => setPhase(phase === "in" ? "out" : "done"), phase === "in" ? INTRO_MS : OUTRO_MS);
    return () => clearTimeout(t);
  }, [phase]);

  if (user?.role === "CUSTOMER") return <Navigate to="/buyer/chat" replace />;
  if (phase !== "done") return <Intro leaving={phase === "out"} onSkip={() => setPhase("done")} />;

  return (
    <div className="mx-auto max-w-3xl animate-rise-in">
      <section
        className="rounded-[2rem] bg-slate-50 p-6 shadow-xl shadow-slate-900/5 ring-1 ring-line sm:p-11"
        aria-labelledby="start-title"
      >
        <span className="grid size-14 place-items-center rounded-2xl bg-brand-600 text-white">
          <UserIcon className="size-7" />
        </span>
        <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-brand-600">Trước khi trò chuyện</p>
        <h1 id="start-title" className="mt-2 text-3xl font-bold tracking-tight sm:text-5xl sm:leading-tight">
          Bạn là người mới hay đã có tài khoản?
        </h1>

        <div className="mt-7 space-y-3.5">
          <Choice
            icon={<SparkleIcon className="size-6" />}
            title="Tôi là người mới"
            hint="Trò chuyện ngay với Trợ lý AI, chỉ cần đăng ký khi gửi yêu cầu xem nhà"
            onClick={() => {
              startGuest();
              navigate("/buyer/chat");
            }}
          />
          <Choice
            icon={<UserIcon className="size-6" />}
            title="Tôi đã có tài khoản"
            hint="Đăng nhập để tiếp tục và xem lại lịch đã đặt"
            onClick={() => navigate("/buyer/login", { state: { from: "/buyer/chat" } })}
          />
        </div>
      </section>
    </div>
  );
}

type IntroPhase = "in" | "out" | "done";
const INTRO_MS = 2600;
const OUTRO_MS = 700;

/** Opening frame: the site's slogan, zooming in gently, then fading into the new/returning question. */
function Intro({ leaving, onSkip }: { leaving: boolean; onSkip: () => void }) {
  return (
    <div className="grid min-h-[60dvh] place-items-center overflow-hidden px-2">
      <button
        type="button"
        onClick={onSkip}
        aria-label="Bỏ qua phần giới thiệu"
        className={`${leaving ? "animate-intro-out" : "animate-intro-in"} relative w-full max-w-3xl cursor-pointer overflow-hidden rounded-[2rem] bg-gradient-to-br from-brand-600 via-brand-500 to-sky-400 px-8 py-14 text-center text-white shadow-2xl shadow-brand-600/25 sm:px-14 sm:py-20`}
      >
        <span aria-hidden="true" className="absolute -right-16 -top-16 size-64 rounded-full bg-white/10 blur-2xl" />
        <span aria-hidden="true" className="absolute -bottom-20 -left-10 size-72 rounded-full bg-sky-200/20 blur-3xl" />
        <span className="relative mx-auto mb-6 grid size-14 place-items-center rounded-2xl bg-white/15 ring-1 ring-white/30">
          <SparkleIcon className="size-7" />
        </span>
        <span className="relative block text-3xl font-bold leading-tight tracking-tight sm:text-5xl sm:leading-tight">
          <span className="block">Tìm nhà Vinhomes</span>
          <span className="block">phù hợp với bạn</span>
          <span className="block text-sky-100">cùng trợ lý AI</span>
        </span>
        <span className="relative mt-6 block text-xs text-white/70">Chạm để bỏ qua</span>
      </button>
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
        <span className="block text-lg font-semibold">{title}</span>
        <span className="mt-0.5 block text-sm text-muted">{hint}</span>
      </span>
      <ArrowRightIcon className="size-5 shrink-0 transition-transform group-hover:translate-x-1 group-hover:text-brand-600" />
    </button>
  );
}
