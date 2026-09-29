import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, call, errorMessage } from "../api/client";
import type { Booking, Recommendation, ViewingTimes } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PropertyCard } from "../components/PropertyCard";
import { BookingBadge } from "../components/ui";
import { dateOf, formatTimeRange, timeOf } from "../lib/format";

interface Message {
  role: "user" | "assistant" | "error";
  text: string;
  recommendations?: Recommendation[];
  viewingTimes?: ViewingTimes | null;
  bookings?: Booking[];
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
      `Chào ${name}! Tôi là trợ lý BookingBot: tôi tìm căn Vinhomes đã được Chủ đầu tư xác thực, ` +
      "kết nối bạn trực tiếp với chủ căn và khớp lịch xem nhà — không cần qua nhiều môi giới.\n" +
      "Bạn đang tìm căn để ở, cho thuê hay đầu tư? Hãy kể cho tôi về dự án bạn quan tâm, ngân sách và số phòng ngủ mong muốn.",
  };
}

function fresh(name: string): Conversation {
  return { id: newId(), messages: [greeting(name)] };
}

// Kept per tab so opening a recommended property and coming back does not lose the chat
function storageKey(userId: number) {
  return `bookingbot.chat.${userId}`;
}

function loadConversation(userId: number, name: string): Conversation {
  try {
    const raw = sessionStorage.getItem(storageKey(userId));
    if (raw) return JSON.parse(raw) as Conversation;
  } catch {
    // Storage blocked or corrupted: start over
  }
  return fresh(name);
}

function saveConversation(userId: number, conversation: Conversation) {
  try {
    sessionStorage.setItem(storageKey(userId), JSON.stringify(conversation));
  } catch {
    // Storage blocked: the chat still works for this page view
  }
}

/** The customer's home: the AI agent asks about their needs and recommends properties (no filter UI). */
export function ChatPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userId = user!.id;
  const name = user!.full_name;
  const [conversation, setConversation] = useState<Conversation>(() => loadConversation(userId, name));
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const append = (message: Message) => setConversation((c) => ({ ...c, messages: [...c.messages, message] }));

  const send = useMutation({
    mutationFn: (message: string) =>
      call(api.POST("/api/v1/chat", { body: { message, conversation_id: conversation.id } })),
    onSuccess: (res) => {
      append({
        role: "assistant",
        text: res.reply,
        recommendations: res.recommendations,
        viewingTimes: res.viewing_times,
        bookings: res.bookings,
      });
      if (res.bookings?.length) queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
    },
    onError: (err) => append({ role: "error", text: errorMessage(err) }),
  });

  useEffect(() => saveConversation(userId, conversation), [userId, conversation]);

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
    setConversation(fresh(name));
    setInput("");
    inputRef.current?.focus();
  }

  const started = conversation.messages.some((m) => m.role === "user");

  return (
    <div className="mx-auto flex max-w-4xl flex-col">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Trợ lý AI</h1>
          <p className="mt-1 text-sm text-muted">Trò chuyện để trợ lý hiểu nhu cầu và gợi ý căn phù hợp nhất cho bạn.</p>
        </div>
        {started && (
          <button type="button" className="btn-secondary btn-sm" onClick={restart} disabled={send.isPending}>
            Cuộc trò chuyện mới
          </button>
        )}
      </div>

      <div className="card flex h-[calc(100dvh-14rem)] min-h-96 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
          {conversation.messages.map((m, i) => (
            <MessageView
              key={i}
              message={m}
              onPickTime={
                i === conversation.messages.length - 1 && !send.isPending
                  ? (iso) => submit(`Tôi chọn xem lúc ${timeOf(iso)} ngày ${dateOf(iso)}`)
                  : undefined
              }
            />
          ))}
          {send.isPending && (
            <p className="flex items-center gap-2 text-sm text-muted">
              <span className="size-3 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
              Trợ lý đang tìm hiểu...
            </p>
          )}
          <div ref={endRef} />
        </div>

        {!started && (
          <div className="flex flex-wrap gap-2 border-t border-line px-4 py-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className="rounded-full border border-line px-3 py-1 text-left text-xs text-muted hover:text-ink"
                onClick={() => submit(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex gap-2 border-t border-line p-3">
          <label htmlFor="chat-input" className="sr-only">
            Tin nhắn
          </label>
          <input
            id="chat-input"
            ref={inputRef}
            className="input"
            placeholder="Nhập nhu cầu của bạn..."
            maxLength={5000}
            autoFocus
            autoComplete="off"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={!input.trim() || send.isPending}>
            Gửi
          </button>
        </form>
      </div>
    </div>
  );
}

function MessageView({ message: m, onPickTime }: { message: Message; onPickTime?: (iso: string) => void }) {
  const times = m.viewingTimes;
  const options = times ? (times.proposals.length > 0 ? times.proposals : (times.alternatives ?? [])) : [];
  const bubble =
    m.role === "user"
      ? "rounded-br-sm bg-brand-600 text-white"
      : m.role === "error"
        ? "rounded-bl-sm border border-red-200 bg-red-50 text-red-800"
        : "rounded-bl-sm bg-stone-100";

  return (
    <div className={`flex flex-col gap-3 ${m.role === "user" ? "items-end" : "items-start"}`}>
      {m.text && <p className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2 text-sm ${bubble}`}>{m.text}</p>}

      {m.recommendations && m.recommendations.length > 0 && (
        <div className="grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {m.recommendations.map((r) => (
            <PropertyCard key={r.property.id} property={r.property} score={r.match_score} matched={r.matched} unmatched={r.unmatched} />
          ))}
        </div>
      )}

      {options.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="Giờ xem đề xuất">
          {options.map((o) => (
            <button
              key={o.start_at}
              type="button"
              disabled={!onPickTime}
              onClick={() => onPickTime?.(o.start_at)}
              className="rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-medium text-brand-700 hover:border-brand-500 disabled:opacity-50"
            >
              {formatTimeRange(o.start_at, o.end_at)}
            </button>
          ))}
        </div>
      )}

      {m.bookings?.map((b) => (
        <div key={b.id} className="card w-full max-w-md space-y-1 p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Deal {b.deal_code}</span>
            <BookingBadge status={b.status} />
          </div>
          <p className="text-muted">{b.property_label}</p>
          <p>{formatTimeRange(b.start_at, b.end_at)}</p>
          <Link to="/bookings" className="text-brand-700 hover:underline">
            Theo dõi tại Lịch xem của tôi
          </Link>
        </div>
      ))}
    </div>
  );
}
