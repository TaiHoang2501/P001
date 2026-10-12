import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";

import { RedBookHomeArt } from "../components/AuthShell";
import { BRAND_GRADIENT_TEXT, BrandLogo } from "../components/Brand";
import { AiBot } from "../buyer/AiBot";
import { ArrowRightIcon, CheckIcon, SparkleIcon } from "../buyer/icons";
import { DemoAccountsTable, OperatorGuide } from "./DemoAccounts";

/**
 * Entry point: the visitor says whether they want to view homes (buyer area with the AI agent)
 * or sell one (BookingBot seller portal, which also hosts the investor/operator console).
 */
export function RoleSelectPage() {
  const navigate = useNavigate();

  // Each area keeps its own sign-in: a signed-in buyer goes on to the chat, a signed-in seller to their page
  const viewHomes = () => navigate("/buyer/start");
  const sellHome = () => navigate("/login");

  const typed = useTypewriter([HEADLINE, SUBTITLE]);
  const done = typed === null;

  return (
    <div className="theme-organic relative min-h-dvh overflow-hidden bg-slate-50 px-4 pb-10 text-ink">
      {/* Soft colour behind the page */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 -top-24 size-[30rem] rounded-full bg-brand-200/50 blur-3xl" />
        <div className="absolute -right-24 bottom-0 size-[28rem] rounded-full bg-orange-200/50 blur-3xl" />
      </div>

      <header className="relative mx-auto flex h-24 w-full max-w-5xl items-center">
        <BrandLogo large />
      </header>

      <main className="relative mx-auto w-full max-w-5xl animate-rise-in" aria-labelledby="role-title">
        <div className="mx-auto max-w-3xl pt-4 text-center sm:pt-8">
          <p className="inline-flex items-center gap-2.5 rounded-full bg-white px-5 py-2.5 text-base font-semibold text-brand-700 shadow-md shadow-brand-600/10 ring-1 ring-brand-100 sm:px-6 sm:py-3 sm:text-lg">
            <SparkleIcon className="size-5" />
            Chào mừng bạn đến với BookingBot
          </p>
          {/* Typed out like the assistant writing; a click shows it all at once */}
          <div className={done ? "" : "cursor-pointer"} onClick={typed?.skip}>
            <h1
              id="role-title"
              aria-label={plain(HEADLINE)}
              className="mt-6 font-display text-[2.6rem] font-bold leading-[1.1] tracking-tight sm:text-6xl"
            >
              <Typed segments={HEADLINE} shown={typed ? typed.shown[0] : Infinity} />
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-muted sm:text-xl">
              <span className="sr-only">{plain(SUBTITLE)}</span>
              <Typed segments={SUBTITLE} shown={typed ? typed.shown[1] : Infinity} />
            </p>
          </div>
        </div>

        {/* The two choices appear once the text is written */}
        <div
          className={`mt-10 grid gap-5 md:grid-cols-2 ${done ? "animate-rise-in" : "pointer-events-none invisible"}`}
          aria-hidden={!done}
        >
          <RoleCard
            onClick={viewHomes}
            panel="bg-gradient-to-br from-[#1463ff] via-[#2f6bff] to-[#5b3df5] text-white"
            art={<AiBot className="size-32 shadow-2xl ring-8 ring-white/15" animated />}
            eyebrow="Người xem nhà"
            title="Tôi muốn tìm căn"
            points={["Trò chuyện với Trợ lý AI, không cần bộ lọc", "Chỉ căn đã xác thực chủ sở hữu", "Đặt lịch xem thẳng với chủ căn"]}
            cta="Bắt đầu tìm nhà"
            ctaClass="bg-white text-brand-700"
          />
          <RoleCard
            onClick={sellHome}
            panel="bg-gradient-to-br from-[#c67139] via-[#d48a55] to-[#b5552a] text-[#fff8ef]"
            art={<RedBookHomeArt />}
            eyebrow="Người bán nhà"
            title="Tôi muốn bán căn"
            points={["Xác thực sổ đỏ / sổ hồng một lần, đăng bán ngay", "AI giới thiệu căn cho người mua phù hợp", "Bạn xác nhận từng lịch xem"]}
            cta="Đến trang người bán"
            ctaClass="bg-[#fff8ef] text-[#9a4a22]"
          />
        </div>

        <p className={`mt-8 text-center text-sm text-muted ${done ? "animate-rise-in" : "invisible"}`}>
          Bạn có thể quay lại màn hình này để đổi vai trò bất cứ lúc nào, bằng cách bấm vào logo BookingBot.
        </p>

        {/* For testers: demo sign-ins and the way into the operator console */}
        <div
          className={`mt-12 grid items-start gap-5 lg:grid-cols-[3fr_2fr] ${done ? "animate-rise-in" : "invisible"}`}
          aria-hidden={!done}
        >
          <DemoAccountsTable />
          <OperatorGuide />
        </div>
      </main>
    </div>
  );
}

function RoleCard({
  onClick,
  panel,
  art,
  eyebrow,
  title,
  points,
  cta,
  ctaClass,
}: {
  onClick: () => void;
  panel: string;
  art: ReactNode;
  eyebrow: string;
  title: string;
  points: string[];
  cta: string;
  ctaClass: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group relative flex flex-col overflow-hidden rounded-[2rem] p-7 text-left shadow-xl shadow-slate-900/10 transition duration-300 hover:-translate-y-1 hover:shadow-2xl sm:p-9 ${panel}`}
    >
      <span aria-hidden="true" className="absolute -right-16 -top-16 size-56 rounded-full bg-white/10" />
      <span aria-hidden="true" className="absolute -bottom-24 -left-12 size-64 rounded-full bg-white/10" />

      <span className="relative text-xs font-bold uppercase tracking-[0.2em] opacity-80">{eyebrow}</span>
      <span className="relative mt-2 font-display text-3xl font-bold">{title}</span>

      <span className="relative my-6 flex h-40 items-center justify-center transition duration-300 group-hover:scale-105">
        {art}
      </span>

      <span className="relative block space-y-2.5">
        {points.map((p) => (
          <span key={p} className="flex items-center gap-2.5 text-sm">
            <span className="grid size-5 shrink-0 place-items-center rounded-full bg-white/20">
              <CheckIcon className="size-3.5" />
            </span>
            {p}
          </span>
        ))}
      </span>

      <span
        className={`relative mt-7 inline-flex items-center justify-center gap-2 self-start rounded-full px-6 py-3 font-bold shadow-sm ${ctaClass}`}
      >
        {cta}
        <ArrowRightIcon className="size-5 transition-transform group-hover:translate-x-1" />
      </span>
    </button>
  );
}

type Segment = { text: string; className?: string };

const HEADLINE: Segment[] = [
  { text: "Bạn muốn làm gì " },
  { text: "hôm nay?", className: BRAND_GRADIENT_TEXT },
];
const SUBTITLE: Segment[] = [
  { text: "Mua và bán căn Vinhomes " },
  { text: "trực tiếp với nhau", className: "font-semibold text-ink" },
  { text: ", " },
  { text: "không qua môi giới", className: "font-semibold text-ink" },
  { text: "." },
  { text: "Chọn vai trò của bạn để bắt đầu.", className: "block" },
];

const plain = (segments: Segment[]) =>
  segments.map((s) => (s.className === "block" ? ` ${s.text}` : s.text)).join("");

/** Milliseconds per character for each block, the pause between blocks, and before the cards appear. */
const SPEED = [28, 10];
const PAUSE = 220;

/**
 * Types the blocks out one after another. Returns how many characters of each block are shown, or null once
 * everything is written (straight away when the visitor asks for reduced motion).
 */
function useTypewriter(blocks: Segment[][]) {
  const lengths = blocks.map((b) => b.reduce((n, s) => n + [...s.text].length, 0));
  const [state, setState] = useState(() => ({
    block: 0,
    count: 0,
    done:
      typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true,
  }));

  useEffect(() => {
    if (state.done) return;
    const len = lengths[state.block];
    let next: typeof state;
    let wait = SPEED[state.block] ?? 30;
    if (state.count < len) next = { ...state, count: state.count + 1 };
    else if (state.block < blocks.length - 1) {
      next = { block: state.block + 1, count: 0, done: false };
      wait = PAUSE;
    } else {
      next = { ...state, done: true };
      wait = PAUSE;
    }
    const t = setTimeout(() => setState(next), wait);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  if (state.done) return null;
  return {
    shown: lengths.map((len, i) => (i < state.block ? len : i === state.block ? state.count : 0)),
    skip: () => setState((s) => ({ ...s, done: true })),
  };
}

/**
 * The first `shown` characters of the segments, with a caret at the end. The rest is laid out but invisible,
 * so the text does not move around while it is being written.
 */
function Typed({ segments, shown }: { segments: Segment[]; shown: number }) {
  let left = shown;
  let caretPlaced = false;
  return (
    <span aria-hidden="true">
      {segments.map((seg, i) => {
        const chars = [...seg.text];
        const visible = chars.slice(0, Math.max(0, left)).join("");
        const rest = chars.slice(Math.max(0, left)).join("");
        left -= chars.length;
        const caret = !caretPlaced && rest.length > 0 && shown !== Infinity && shown > 0;
        if (caret) caretPlaced = true;
        return (
          <span key={i} className={seg.className}>
            {visible}
            {caret && <Caret />}
            <span className="invisible">{rest}</span>
          </span>
        );
      })}
    </span>
  );
}

function Caret() {
  return (
    <span className="relative inline-block h-[0.95em] w-0 align-[-0.1em]">
      <span className="absolute inset-y-0 left-0 w-[3px] animate-pulse rounded-full bg-brand-600" />
    </span>
  );
}
