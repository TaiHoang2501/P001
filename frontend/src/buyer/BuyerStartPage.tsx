import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { startGuest } from "./guest";
import { AiBot } from "./AiBot";
import { ArrowLeftIcon, ArrowRightIcon, CalendarIcon, CheckCircleIcon, SparkleIcon, UserIcon } from "./icons";

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
    <div className="mx-auto max-w-5xl animate-rise-in py-4">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted hover:text-ink">
        <ArrowLeftIcon className="size-4" />
        Đổi vai trò
      </Link>

      <div className="mx-auto mt-4 max-w-3xl text-center">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-600">Trước khi trò chuyện</p>
        <h1 id="start-title" className="mt-3 font-display text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
          Bạn là người mới hay đã có tài khoản?
        </h1>
      </div>

      <div className="mt-9 grid gap-5 md:grid-cols-[1.15fr_1fr]" aria-labelledby="start-title">
        {/* New buyers: straight into the chat as a guest */}
        <button
          type="button"
          onClick={() => {
            startGuest();
            navigate("/buyer/chat");
          }}
          className="group relative flex flex-col overflow-hidden rounded-[2rem] bg-gradient-to-br from-[#1463ff] via-[#2f6bff] to-[#5b3df5] p-7 text-left text-white shadow-xl shadow-brand-600/20 transition duration-300 hover:-translate-y-1 hover:shadow-2xl sm:p-9"
        >
          <span aria-hidden="true" className="absolute -right-16 -top-16 size-56 rounded-full bg-white/10" />
          <span aria-hidden="true" className="absolute -bottom-24 -left-12 size-64 rounded-full bg-white/10" />
          <span className="relative flex items-start justify-between gap-4">
            <span>
              <span className="inline-block rounded-full bg-white/20 px-3 py-1 text-xs font-bold">
                Không cần đăng ký để bắt đầu
              </span>
              <span className="mt-3 block font-display text-3xl font-bold">Tôi là người mới</span>
              <span className="mt-1 block text-white/85">Trò chuyện ngay với Trợ lý AI.</span>
            </span>
            <AiBot className="size-20 shrink-0 shadow-xl ring-4 ring-white/20 transition group-hover:scale-105" animated />
          </span>

          <ol className="relative mt-7 space-y-3">
            {[
              ["Kể nhu cầu", "Ngân sách, số phòng ngủ, dự án bạn thích..."],
              ["Xem căn phù hợp", "Trợ lý gợi ý căn đã xác thực, kèm lý do."],
              ["Đặt lịch xem", "Chỉ lúc này mới cần số điện thoại để nhận mã OTP."],
            ].map(([t, d], i) => (
              <li key={t} className="flex gap-3">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white text-sm font-bold text-brand-700">
                  {i + 1}
                </span>
                <span>
                  <span className="block font-semibold">{t}</span>
                  <span className="block text-sm text-white/80">{d}</span>
                </span>
              </li>
            ))}
          </ol>

          <span className="relative mt-8 inline-flex items-center gap-2 self-start rounded-full bg-white px-6 py-3 font-bold text-brand-700 shadow-sm">
            Trò chuyện ngay
            <ArrowRightIcon className="size-5 transition-transform group-hover:translate-x-1" />
          </span>
        </button>

        {/* Returning buyers: sign in to see earlier viewings */}
        <button
          type="button"
          onClick={() => navigate("/buyer/login", { state: { from: "/buyer/chat" } })}
          className="group flex flex-col rounded-[2rem] bg-white p-7 text-left shadow-xl shadow-slate-900/5 ring-1 ring-line transition duration-300 hover:-translate-y-1 hover:shadow-2xl hover:ring-brand-300 sm:p-9"
        >
          <span className="grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-600">
            <UserIcon className="size-7" />
          </span>
          <span className="mt-5 block font-display text-3xl font-bold">Tôi đã có tài khoản</span>
          <span className="mt-1 block text-muted">Đăng nhập bằng số điện thoại và mã OTP.</span>

          <span className="mt-7 block space-y-3">
            {[
              [CalendarIcon, "Xem lại các lịch xem đã đặt"],
              [CheckCircleIcon, "Mã QR vào cửa cho lịch đã xác nhận"],
              [SparkleIcon, "Nhận thông báo khi chủ căn trả lời"],
            ].map(([Icon, t]) => {
              const I = Icon as typeof CalendarIcon;
              return (
                <span key={t as string} className="flex items-center gap-3 text-sm">
                  <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-slate-100 text-ink">
                    <I className="size-4" />
                  </span>
                  {t as string}
                </span>
              );
            })}
          </span>

          <span className="mt-auto pt-8">
            <span className="inline-flex items-center gap-2 rounded-full border border-ink/15 px-6 py-3 font-bold transition group-hover:border-brand-600 group-hover:bg-brand-600 group-hover:text-white">
              Đăng nhập
              <ArrowRightIcon className="size-5 transition-transform group-hover:translate-x-1" />
            </span>
          </span>
        </button>
      </div>
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
