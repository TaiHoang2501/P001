import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import { api, call, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import type { Booking, Recommendation, User, ViewingTimes } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { BookingBadge } from "../components/ui";
import { CRITERION, dateOf, formatTimeRange, formatVnd, timeOf } from "../lib/format";
import { chatStorageKey } from "./guest";
import { GuestSignup } from "./GuestSignup";
import { SendIcon, SparkleIcon } from "./icons";
import { featureLine, imagesOf, MatchBadge, PropertyImage, specLine } from "./shared";

type PendingViewing = components["schemas"]["PendingViewingRequest"];

interface Message {
  role: "user" | "assistant" | "error";
  text: string;
  recommendations?: Recommendation[];
  viewingTimes?: ViewingTimes | null;
  bookings?: Booking[];
  // Guest chat: the agent needs an account to go on (e.g. to send this viewing request)
  needsAccount?: boolean;
  pendingViewing?: PendingViewing | null;
}

interface Conversation {
  id: string;
  messages: Message[];
}

const SUGGESTIONS = [
  "Tôi cần căn 2 phòng ngủ ở Ocean Park, dưới 3,5 tỷ",
  "Gia đình 4 người, thích view hồ, hướng Đông Nam",
  "Tìm căn studio để cho thuê",
];

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function greeting(name: string): Message {
  return {
    role: "assistant",
    text:
      `Xin chào ${name}! Bạn đang tìm căn Vinhomes như thế nào? ` +
      "Bạn có thể mô tả bằng ngôn ngữ tự nhiên: dự án, ngân sách, số phòng ngủ, tầng, view, mục đích mua...",
  };
}

function fresh(name: string): Conversation {
  return { id: newId(), messages: [greeting(name)] };
}

// Kept per tab so opening a recommended property and coming back does not lose the chat.
// userId null = guest (a new buyer without an account yet).
function loadConversation(userId: number | null, name: string): Conversation {
  try {
    const raw = sessionStorage.getItem(chatStorageKey(userId));
    if (raw) return JSON.parse(raw) as Conversation;
  } catch {
    // Storage blocked or corrupted: start over
  }
  return fresh(name);
}

function saveConversation(userId: number | null, conversation: Conversation) {
  try {
    sessionStorage.setItem(chatStorageKey(userId), JSON.stringify(conversation));
  } catch {
    // Storage blocked: the chat still works for this page view
  }
}

/** The agent writes light markdown: render **bold**, keep everything else as text. */
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
      )}
    </>
  );
}

/** Backend criterion text -> Vietnamese display: "0 - 3.50 tỷ" -> "≤ 3,5 tỷ", "2" bedrooms -> "2 PN" */
function wantedLabel(criterion: string, wanted: string): string {
  if (criterion === "bedrooms") return `${wanted} PN`;
  const vn = wanted.replace(/(\d+)\.(\d+)/g, (_, a: string, b: string) => {
    const frac = b.replace(/0+$/, "");
    return frac ? `${a},${frac}` : a;
  });
  return vn.replace(/^0 - /, "≤ ");
}

/** What the agent understood, as label/value pairs (wireframe 1.2 summary, 1.3 "Nhu cầu của bạn"). */
function criteriaOf(recs: Recommendation[]): { label: string; value: string }[] {
  if (recs.length === 0) return [];
  const out: { label: string; value: string }[] = [];
  const projects = new Set(recs.map((r) => r.property.project_name));
  if (projects.size === 1) out.push({ label: "Dự án", value: [...projects][0] });
  for (const c of [...recs[0].matched, ...recs[0].unmatched]) {
    out.push({ label: CRITERION[c.criterion] ?? c.criterion, value: wantedLabel(c.criterion, c.wanted) });
  }
  return out;
}

/**
 * Wireframe 1.2 + 1.3: chat with the AI agent; its latest recommendations are listed beside the chat.
 * New buyers chat as guests; when they confirm a viewing, a phone + OTP sign-up appears in the chat.
 */
export function BuyerChatPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userId = user?.role === "CUSTOMER" ? user.id : null;
  const name = userId !== null ? user!.full_name : "bạn";
  const [conversation, setConversation] = useState<Conversation>(() => loadConversation(userId, name));
  const [input, setInput] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const append = (message: Message) => setConversation((c) => ({ ...c, messages: [...c.messages, message] }));

  const send = useMutation({
    mutationFn: (message: string) => {
      const body = { message, conversation_id: conversation.id };
      return userId === null
        ? call(api.POST("/api/v1/chat/guest", { body }))
        : call(api.POST("/api/v1/chat", { body }));
    },
    onSuccess: (res) => {
      append({
        role: "assistant",
        text: res.reply,
        recommendations: res.recommendations,
        viewingTimes: res.viewing_times,
        bookings: res.bookings,
        needsAccount: res.needs_account,
        pendingViewing: res.pending_viewing,
      });
      if (res.bookings?.length) queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
    },
    onError: (err) => append({ role: "error", text: errorMessage(err) }),
  });

  useEffect(() => saveConversation(userId, conversation), [userId, conversation]);

  // The guest just signed up: send the viewing request the agent prepared, as the new account
  const sendPending = useMutation({
    mutationFn: (pending: PendingViewing) =>
      call(
        api.POST("/api/v1/bookings", {
          body: {
            property_id: pending.property_id,
            start_at: pending.start_at,
            buyer_windows: pending.buyer_windows ?? [],
            note: pending.note ?? null,
          },
        }),
      ),
    onSuccess: (booking) => {
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
      append({
        role: "assistant",
        text:
          `Đã gửi yêu cầu xem nhà tới chủ căn — mã Deal ${booking.deal_code}. ` +
          "Lịch chỉ có hiệu lực khi chủ căn xác nhận; bạn theo dõi trạng thái ngay bên dưới.",
        bookings: [booking],
      });
    },
    onError: (err) => append({ role: "error", text: errorMessage(err) }),
  });

  function onSignedUp(account: User, pending: PendingViewing | null | undefined) {
    // The sign-up prompt is answered: hide it on every earlier message
    setConversation((c) => ({ ...c, messages: c.messages.map((m) => (m.needsAccount ? { ...m, needsAccount: false } : m)) }));
    if (pending) sendPending.mutate(pending);
    else
      append({
        role: "assistant",
        text: `Chào ${account.full_name}, tài khoản của bạn đã sẵn sàng. Mình tiếp tục nhé!`,
      });
  }

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversation.messages.length, send.isPending]);

  function submit(text: string) {
    const message = text.trim();
    if (!message || send.isPending) return;
    append({ role: "user", text: message });
    setInput("");
    send.mutate(message);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(input);
  }

  function restart() {
    setMenuOpen(false);
    setConversation(fresh(name));
    setInput("");
    inputRef.current?.focus();
  }

  const started = conversation.messages.some((m) => m.role === "user");
  // Guests see the sign-up prompt under the latest reply that needs an account
  let signupAt = -1;
  if (userId === null) conversation.messages.forEach((m, i) => m.needsAccount && (signupAt = i));
  const latest = [...conversation.messages].reverse().find((m) => m.recommendations?.length)?.recommendations ?? [];

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
      <section className="card flex h-[calc(100dvh-12rem)] min-h-[28rem] flex-col overflow-hidden shadow-sm" aria-label="Chat AI">
        <header className="flex items-center gap-3 border-b border-line px-5 py-4">
          <AgentAvatar />
          <div className="min-w-0 flex-1">
            <h1 className="font-semibold">AI Agent</h1>
            <p className="text-xs text-muted">
              Trợ lý tìm nhà Vinhomes{userId === null && " · Bạn đang trò chuyện với tư cách khách"}
            </p>
          </div>
          <div className="relative">
            <button
              type="button"
              className="grid size-9 place-items-center rounded-lg text-muted hover:bg-slate-100 hover:text-ink"
              aria-label="Tùy chọn"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
            >
              <span className="text-xl leading-none">⋮</span>
            </button>
            {menuOpen && (
              <div className="card absolute right-0 z-10 mt-1 w-56 overflow-hidden py-1 shadow-lg">
                <button
                  type="button"
                  className="block w-full px-4 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                  disabled={!started || send.isPending}
                  onClick={restart}
                >
                  Cuộc trò chuyện mới
                </button>
                <Link to="/buyer/bookings" className="block px-4 py-2 text-sm hover:bg-slate-50">
                  Lịch xem của tôi
                </Link>
              </div>
            )}
          </div>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto bg-slate-50/60 p-5" aria-live="polite">
          {conversation.messages.map((m, i) => (
            <MessageView
              key={i}
              message={m}
              onPickTime={
                i === conversation.messages.length - 1 && !send.isPending
                  ? (iso) => submit(`Tôi chọn xem lúc ${timeOf(iso)} ngày ${dateOf(iso)}`)
                  : undefined
              }
              signup={
                i === signupAt ? (
                  <div className="max-w-md">
                    <GuestSignup onDone={(u) => onSignedUp(u, m.pendingViewing)} />
                  </div>
                ) : undefined
              }
            />
          ))}
          {sendPending.isPending && <p className="pl-12 text-sm text-muted">Đang gửi yêu cầu xem nhà...</p>}
          {send.isPending && (
            <div className="flex items-center gap-3">
              <AgentAvatar />
              <p className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-line">
                <Dot delay="0ms" />
                <Dot delay="150ms" />
                <Dot delay="300ms" />
                <span className="sr-only">Trợ lý đang trả lời</span>
              </p>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {!started && (
          <div className="flex flex-wrap gap-2 border-t border-line px-5 py-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className="rounded-full border border-line bg-white px-3 py-1.5 text-left text-xs text-muted hover:border-brand-500 hover:text-brand-700"
                onClick={() => submit(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex items-center gap-2 border-t border-line bg-white p-3">
          <label htmlFor="chat-input" className="sr-only">
            Tin nhắn
          </label>
          <input
            id="chat-input"
            ref={inputRef}
            className="input rounded-xl py-2.5"
            placeholder={started ? "Nhập thêm yêu cầu..." : "Nhập nhu cầu của bạn..."}
            maxLength={5000}
            autoFocus
            autoComplete="off"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button
            type="submit"
            className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40"
            aria-label="Gửi"
            disabled={!input.trim() || send.isPending}
          >
            <SendIcon className="size-5" />
          </button>
        </form>
      </section>

      <ResultsPanel recommendations={latest} />
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return <span className="size-1.5 animate-bounce rounded-full bg-brand-500" style={{ animationDelay: delay }} />;
}

function AgentAvatar() {
  return (
    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-brand-600">
      <SparkleIcon className="size-5" />
    </span>
  );
}

function MessageView({
  message: m,
  onPickTime,
  signup,
}: {
  message: Message;
  onPickTime?: (iso: string) => void;
  signup?: ReactNode;
}) {
  const times = m.viewingTimes;
  const options = times ? (times.proposals.length > 0 ? times.proposals : (times.alternatives ?? [])) : [];
  const criteria = criteriaOf(m.recommendations ?? []);

  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[80%] whitespace-pre-line rounded-2xl rounded-tr-sm bg-brand-100 px-4 py-2.5 text-sm text-ink">{m.text}</p>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <AgentAvatar />
      <div className="min-w-0 flex-1 space-y-3">
        {m.text && (
          <p
            className={`w-fit max-w-[90%] whitespace-pre-line rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm ${
              m.role === "error" ? "border border-red-200 bg-red-50 text-red-800" : "bg-white shadow-sm ring-1 ring-line"
            }`}
          >
            <RichText text={m.text} />
          </p>
        )}

        {criteria.length > 0 && (
          <dl className="grid max-w-lg grid-cols-2 gap-2 sm:grid-cols-3">
            {criteria.map((c) => (
              <div key={c.label} className="rounded-xl border border-line bg-white px-3 py-2">
                <dt className="text-[11px] text-muted">{c.label}</dt>
                <dd className="truncate text-sm font-medium">{c.value}</dd>
              </div>
            ))}
          </dl>
        )}

        {/* On wide screens the results panel shows these; inline on phones/tablets */}
        {m.recommendations && m.recommendations.length > 0 && (
          <ul className="space-y-2 lg:hidden">
            {m.recommendations.map((r) => (
              <li key={r.property.id}>
                <ResultRow rec={r} />
              </li>
            ))}
          </ul>
        )}

        {options.length > 0 && (
          <div className="flex flex-wrap gap-1.5" aria-label="Giờ xem đề xuất">
            {options.map((o) => (
              <button
                key={o.start_at}
                type="button"
                disabled={!onPickTime}
                onClick={() => onPickTime?.(o.start_at)}
                className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 hover:border-brand-500 disabled:opacity-50"
              >
                {formatTimeRange(o.start_at, o.end_at)}
              </button>
            ))}
          </div>
        )}

        {m.bookings?.map((b) => (
          <div key={b.id} className="card w-full max-w-md space-y-1 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">Deal {b.deal_code}</span>
              <BookingBadge status={b.status} />
            </div>
            <p className="text-muted">{b.property_label}</p>
            <p>{formatTimeRange(b.start_at, b.end_at)}</p>
            <Link to={`/buyer/bookings/${b.id}`} className="font-medium text-brand-700 hover:underline">
              Theo dõi trạng thái
            </Link>
          </div>
        ))}

        {signup}
      </div>
    </div>
  );
}

/** Wireframe 1.3: needs as chips + the matching properties. */
function ResultsPanel({ recommendations }: { recommendations: Recommendation[] }) {
  const criteria = criteriaOf(recommendations);
  return (
    <aside className="card hidden h-[calc(100dvh-12rem)] min-h-[28rem] flex-col overflow-hidden shadow-sm lg:flex" aria-label="Kết quả đề xuất">
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-sm font-semibold">Nhu cầu của bạn</h2>
        {criteria.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {criteria.map((c) => (
              <li key={c.label} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-ink" title={c.label}>
                {c.value}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-muted">Trợ lý sẽ tóm tắt tiêu chí sau khi hiểu nhu cầu của bạn.</p>
        )}
      </div>
      <p className="border-b border-line px-5 py-2.5 text-sm font-medium text-brand-600">
        <span className="border-b-2 border-brand-600 pb-2.5">Căn phù hợp ({recommendations.length})</span>
      </p>
      <div className="flex-1 overflow-y-auto p-4">
        {recommendations.length === 0 ? (
          <p className="px-2 py-10 text-center text-sm text-muted">Chưa có căn đề xuất. Hãy kể cho AI Agent về căn bạn mong muốn.</p>
        ) : (
          <ul className="space-y-3">
            {recommendations.map((r) => (
              <li key={r.property.id}>
                <ResultRow rec={r} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function ResultRow({ rec }: { rec: Recommendation }) {
  const p = rec.property;
  const scored = rec.matched.length + rec.unmatched.length > 0;
  return (
    <article className="flex gap-3 rounded-xl border border-line bg-white p-2.5">
      <PropertyImage src={imagesOf(p)[0]?.url} alt={`Căn ${p.unit_code}`} className="size-20 shrink-0 rounded-lg sm:h-24 sm:w-28" />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-2">
          <h3 className="truncate text-sm font-semibold">{p.unit_code}</h3>
          {scored && <MatchBadge score={rec.match_score} />}
        </div>
        <p className="truncate text-xs text-muted">{p.project_name}</p>
        <p className="truncate text-xs text-muted">{specLine(p)}</p>
        <p className="truncate text-xs text-muted">{featureLine(p)}</p>
        <div className="mt-auto flex flex-wrap items-end justify-between gap-2 pt-1">
          <p className="font-semibold">{formatVnd(p.price_vnd)}</p>
          <Link to={`/buyer/properties/${p.id}`} className="btn btn-sm border border-brand-600 text-brand-600 hover:bg-brand-50">
            Xem chi tiết
          </Link>
        </div>
      </div>
    </article>
  );
}
