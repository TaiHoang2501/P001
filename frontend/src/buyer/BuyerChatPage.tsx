import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useSearchParams } from "react-router";

import { api, call, errorMessage, streamChat } from "../api/client";
import type { components } from "../api/schema";
import type {
  Booking,
  ChatResponse,
  Property,
  Recommendation,
  User,
  ViewingTimes,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { BookingBadge } from "../components/ui";
import {
  CRITERION,
  dateOf,
  formatTimeRange,
  formatVnd,
  timeOf,
} from "../lib/format";
import { ENDED } from "./bookingStatus";
import { BookingsListCard } from "./BookingsListCard";
import { BookingStatusCard } from "./BookingStatusCard";
import { chatStorageKey } from "./guest";
import { GuestSignup } from "./GuestSignup";
import { SendIcon } from "./icons";
import { AiBot } from "./AiBot";
import { PropertyDetailCard, useProperty } from "./PropertyDetailCard";
import {
  featureLine,
  imagesOf,
  MatchBadge,
  PropertyImage,
  specLine,
} from "./shared";
import { ViewingScheduler } from "./ViewingScheduler";

type PendingViewing = components["schemas"]["PendingViewingRequest"];

// Shown in the chat instead of separate pages; each card has "← Quay lại" to close it
type Card =
  | { kind: "property"; propertyId: number }
  | {
      kind: "schedule";
      propertyId: number;
      reschedule?: Booking;
      done?: boolean;
    }
  | { kind: "status"; bookingId: number }
  | { kind: "bookings" };

interface Message {
  id?: string;
  role: "user" | "assistant" | "error";
  text: string;
  recommendations?: Recommendation[];
  viewingTimes?: ViewingTimes | null;
  bookings?: Booking[];
  // Guest chat: the agent needs an account to go on (e.g. to send this viewing request)
  needsAccount?: boolean;
  pendingViewing?: PendingViewing | null;
  card?: Card;
  // The agent's own messages (status changes, follow-ups): homes to open, a viewing to track, quick replies
  propertyIds?: number[];
  trackBookingId?: number;
  replies?: string[];
}

interface Conversation {
  id: string;
  messages: Message[];
  // Last seen state of each viewing ("status|start|proposed"), so a change is told once
  known?: Record<string, string>;
  // Agent notifications already posted, and when this chat started (older ones are not replayed)
  seenNotes?: number[];
  since?: string;
}

const AGENT_EVENTS = new Set(["AGENT_FOLLOWUP", "AGENT_NEW_MATCH"]);

function signature(b: Booking): string {
  return `${b.status}|${b.start_at}|${b.proposed_start_at ?? ""}`;
}

/** What the agent says when a viewing changed without the buyer doing it (null: nothing worth saying). */
function statusNews(
  previous: string,
  b: Booking,
): Pick<Message, "text" | "replies"> | null {
  const [was, wasStart] = previous.split("|") as [Booking["status"], string];
  const home = `**${b.property_label}**`;
  const when = formatTimeRange(b.start_at, b.end_at);
  const other = [
    `Tìm giờ xem khác cho căn ${b.property_label}`,
    "Tìm căn tương tự",
  ];
  switch (b.status) {
    case "CONFIRMED":
      if (was === "RESCHEDULE_REQUESTED")
        return b.start_at !== wasStart
          ? { text: `Chủ căn đã đồng ý đổi lịch xem ${home} sang ${when}.` }
          : {
              text: `Chủ căn chưa nhận giờ mới cho ${home}; lịch cũ ${when} vẫn giữ nguyên.`,
            };
      if (was === "CONFIRMED")
        return b.start_at !== wasStart
          ? { text: `Lịch xem ${home} đã chuyển sang ${when}.` }
          : null;
      return {
        text:
          `Tin vui: chủ căn đã xác nhận lịch xem ${home} lúc ${when}.` +
          (b.hold_status === "ACTIVE"
            ? " Căn được giữ riêng cho bạn trong khung giờ này."
            : "") +
          " Mình sẽ nhắc bạn trước buổi xem.",
      };
    case "REJECTED":
      return {
        text:
          `Chủ căn chưa nhận lịch xem ${home} (${when})${b.rejection_reason ? `: ${b.rejection_reason}` : ""}. ` +
          "Bạn muốn mình tìm giờ khác hay căn tương tự?",
        replies: other,
      };
    case "CANCELLED":
      return {
        text: `Lịch xem ${home} (${when}) đã bị hủy. Mình có thể tìm giờ hoặc căn khác cho bạn.`,
        replies: other,
      };
    case "COMPLETED":
      return {
        text: `Buổi xem ${home} đã hoàn tất. Bạn thấy căn thế nào? Muốn xem thêm căn khác cứ nhắn mình nhé.`,
      };
    default:
      return null;
  }
}

// What the assistant is doing while it works, by the tool it called
const TOOL_STATUS: Record<string, string> = {
  list_projects: "Đang xem danh sách dự án...",
  search_properties: "Đang tìm căn phù hợp...",
  get_property_detail: "Đang xem chi tiết căn...",
  get_seller_status: "Đang kiểm tra chủ căn...",
  check_seller_availability: "Đang xem lịch trống của chủ căn...",
  check_property_availability: "Đang khớp lịch xem...",
  get_deal_status: "Đang kiểm tra lịch xem của bạn...",
  get_booking_status: "Đang kiểm tra lịch xem của bạn...",
  create_viewing_request: "Đang gửi yêu cầu xem nhà...",
  cancel_viewing: "Đang hủy lịch xem...",
  reschedule_viewing: "Đang đổi giờ xem...",
  create_human_escalation: "Đang chuyển cho nhân viên hỗ trợ...",
};

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
  return {
    id: newId(),
    messages: [greeting(name)],
    since: new Date().toISOString(),
  };
}

// Kept per tab so opening a recommended property and coming back does not lose the chat.
// userId null = guest (a new buyer without an account yet).
function loadConversation(userId: number | null, name: string): Conversation {
  try {
    const raw = sessionStorage.getItem(chatStorageKey(userId));
    if (raw)
      return {
        since: new Date().toISOString(),
        ...(JSON.parse(raw) as Conversation),
      };
  } catch {
    // Storage blocked or corrupted: start over
  }
  return fresh(name);
}

function saveConversation(userId: number | null, conversation: Conversation) {
  try {
    sessionStorage.setItem(
      chatStorageKey(userId),
      JSON.stringify(conversation),
    );
  } catch {
    // Storage blocked: the chat still works for this page view
  }
}

/** The agent writes light markdown: render **bold**, keep everything else as text. */
function RichText({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/(\*\*[^*]+\*\*)/g)
        .map((part, i) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={i}>{part.slice(2, -2)}</strong>
          ) : (
            part
          ),
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
function criteriaOf(
  recs: Recommendation[],
): { label: string; value: string }[] {
  if (recs.length === 0) return [];
  const out: { label: string; value: string }[] = [];
  const projects = new Set(recs.map((r) => r.property.project_name));
  if (projects.size === 1)
    out.push({ label: "Dự án", value: [...projects][0] });
  for (const c of [...recs[0].matched, ...recs[0].unmatched]) {
    out.push({
      label: CRITERION[c.criterion] ?? c.criterion,
      value: wantedLabel(c.criterion, c.wanted),
    });
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
  const [conversation, setConversation] = useState<Conversation>(() =>
    loadConversation(userId, name),
  );
  const [input, setInput] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  // The home the buyer last opened in the chat, so "đặt căn này chiều mai" reaches the agent with its id
  const [viewing, setViewing] = useState<{ id: number; code?: string } | null>(
    null,
  );
  const [searchParams, setSearchParams] = useSearchParams();
  // The reply being written (streamed), or what the assistant is doing meanwhile
  // `final`: the finished turn, shown once the typing-out has caught up with the streamed text
  const [live, setLive] = useState<{ text: string; status: string | null; final?: ChatResponse } | null>(null);
  const streamed = useRef("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // Going back scrolls to the previous step instead of the end
  const skipScroll = useRef(false);

  const append = (message: Message) =>
    setConversation((c) => ({
      ...c,
      messages: [...c.messages, { id: newId(), ...message }],
    }));

  // The buyer's own changes are already in the chat: remember them so they are not told again as news
  const markKnown = (bookings: Booking[]) =>
    setConversation((c) => ({
      ...c,
      known: {
        ...(c.known ?? {}),
        ...Object.fromEntries(
          bookings.map((b) => [String(b.id), signature(b)]),
        ),
      },
    }));

  // Seller answers, reschedules, cancellations: the agent tells the buyer here, without a reload
  const myBookings = useQuery({
    queryKey: ["my-bookings"],
    queryFn: () => call(api.GET("/api/v1/bookings")),
    enabled: userId !== null,
    refetchInterval: 30_000,
  });
  useEffect(() => {
    const bookings = myBookings.data;
    if (!bookings) return;
    setConversation((c) => {
      const known = { ...(c.known ?? {}) };
      const news: Message[] = [];
      for (const b of bookings) {
        const previous = known[String(b.id)];
        const now = signature(b);
        if (previous === now) continue;
        const was = previous?.split("|")[0] as Booking["status"] | undefined;
        // An ended viewing does not come back (a late, stale answer would only confuse)
        if (was && (ENDED.has(was) || was === "COMPLETED")) continue;
        known[String(b.id)] = now;
        // First look (new chat / new viewing): remember silently
        const said = c.known && previous ? statusNews(previous, b) : null;
        if (said)
          news.push({
            id: newId(),
            role: "assistant",
            trackBookingId: b.id,
            ...said,
          });
      }
      return {
        ...c,
        known,
        messages: news.length ? [...c.messages, ...news] : c.messages,
      };
    });
  }, [myBookings.data]);

  // Agent follow-ups and new matching homes (sent while the buyer was away) arrive as agent messages
  const notes = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => call(api.GET("/api/v1/notifications")),
    enabled: userId !== null,
    refetchInterval: 30_000,
  });
  useEffect(() => {
    const list = notes.data;
    if (!list) return;
    setConversation((c) => {
      const seen = new Set(c.seenNotes ?? []);
      const since = c.since ? Date.parse(c.since) : 0;
      const unseen = list
        .filter(
          (n) =>
            AGENT_EVENTS.has(n.event_type) &&
            !seen.has(n.id) &&
            n.sent_at &&
            Date.parse(n.sent_at) > since,
        )
        .reverse();
      if (unseen.length === 0) return c;
      const news: Message[] = unseen.map((n) => {
        const payload = (n.payload ?? {}) as {
          property_ids?: number[];
          property_id?: number;
        };
        return {
          id: newId(),
          role: "assistant",
          text: `**${n.title}**\n${n.body}`,
          propertyIds:
            payload.property_ids ??
            (payload.property_id ? [payload.property_id] : []),
          trackBookingId: n.booking_id ?? undefined,
        };
      });
      return {
        ...c,
        seenNotes: [...seen, ...unseen.map((n) => n.id)],
        messages: [...c.messages, ...news],
      };
    });
  }, [notes.data]);

  const send = useMutation({
    mutationFn: (message: string) => {
      const context = viewing
        ? `(Khách đang xem căn #${viewing.id}${viewing.code ? ` – ${viewing.code}` : ""})
`
        : "";
      const body = {
        message: context + message,
        conversation_id: conversation.id,
      };
      streamed.current = "";
      setLive({ text: "", status: null });
      // The reply appears word by word; cards and bookings come with the final event
      return streamChat(userId === null ? "/api/v1/chat/guest/stream" : "/api/v1/chat/stream", body, {
        onToken: (text) => {
          streamed.current += text;
          setLive({ text: streamed.current, status: null });
        },
        onTools: (names) => {
          streamed.current = "";
          setLive({ text: "", status: TOOL_STATUS[names[0]] ?? "Đang xử lý..." });
        },
      });
    },
    onSuccess: (res) => {
      // Let the typing-out finish first (StreamingText calls finishTurn); nothing typed -> show it now
      if (streamed.current) setLive((l) => (l ? { ...l, final: res } : l));
      else finishTurn(res);
    },
    onError: (err) => {
      setLive(null);
      append({ role: "error", text: errorMessage(err) });
    },
  });

  function finishTurn(res: ChatResponse) {
    setLive(null);
    append({
        role: "assistant",
        text: res.reply,
        recommendations: res.recommendations,
        viewingTimes: res.viewing_times,
        bookings: res.bookings,
        needsAccount: res.needs_account,
        pendingViewing: res.pending_viewing,
      });
      if (res.bookings?.length) {
        markKnown(res.bookings);
        queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
      }
  }

  useEffect(
    () => saveConversation(userId, conversation),
    [userId, conversation],
  );

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
      markKnown([booking]);
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

  function onSignedUp(
    account: User,
    pending: PendingViewing | null | undefined,
  ) {
    // The sign-up prompt is answered: hide it on every earlier message
    setConversation((c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.needsAccount ? { ...m, needsAccount: false } : m,
      ),
    }));
    if (pending) sendPending.mutate(pending);
    else
      append({
        role: "assistant",
        text: `Chào ${account.full_name}, tài khoản của bạn đã sẵn sàng. Mình tiếp tục nhé!`,
      });
  }

  // Everything happens in this chat: details, viewing-time picker, status and the buyer's viewings open as cards here
  const addCard = (card: Card) => append({ role: "assistant", text: "", card });

  function openProperty(id: number, code?: string) {
    setViewing({ id, code });
    addCard({ kind: "property", propertyId: id });
  }

  function openSchedule(p: Pick<Property, "id" | "unit_code">) {
    setViewing({ id: p.id, code: p.unit_code });
    addCard({ kind: "schedule", propertyId: p.id });
  }

  function openReschedule(b: Booking) {
    setViewing({ id: b.property_id });
    addCard({ kind: "schedule", propertyId: b.property_id, reschedule: b });
  }

  /** One card per viewing / one list: opening it again moves it to the bottom. */
  function openOnce(card: Card, same: (c: Card) => boolean) {
    setConversation((c) => ({
      ...c,
      messages: [
        ...c.messages.filter((m) => !(m.card && same(m.card))),
        { id: newId(), role: "assistant", text: "", card },
      ],
    }));
  }

  function openStatus(bookingId: number) {
    openOnce(
      { kind: "status", bookingId },
      (c) => c.kind === "status" && c.bookingId === bookingId,
    );
  }

  function openBookings() {
    setMenuOpen(false);
    openOnce({ kind: "bookings" }, (c) => c.kind === "bookings");
  }

  /** "← Quay lại": close this card and show the step before it. */
  function goBack(index: number) {
    const previousHome = conversation.messages
      .slice(0, index)
      .reverse()
      .find(
        (m) => m.card?.kind === "property" || m.card?.kind === "schedule",
      )?.card;
    setViewing(
      previousHome && "propertyId" in previousHome
        ? { id: previousHome.propertyId }
        : null,
    );
    skipScroll.current = true;
    setConversation((c) => ({
      ...c,
      messages: c.messages.filter((_, i) => i !== index),
    }));
    requestAnimationFrame(() =>
      document
        .getElementById(`msg-${Math.max(index - 1, 0)}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }

  function onScheduled(booking: Booking, rescheduled: boolean) {
    markKnown([booking]);
    setConversation((c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.card?.kind === "schedule" &&
        m.card.propertyId === booking.property_id &&
        !m.card.done &&
        !!m.card.reschedule === rescheduled
          ? { ...m, card: { ...m.card, done: true } }
          : m,
      ),
    }));
    append(
      rescheduled
        ? {
            role: "assistant",
            text:
              booking.status === "REQUESTED"
                ? `Đã đổi yêu cầu xem ${booking.property_label} sang ${formatTimeRange(booking.start_at, booking.end_at)}. ` +
                  "Chủ căn đã được báo và vẫn cần xác nhận giờ mới; mình sẽ báo bạn ngay khi có phản hồi."
                : `Đã gửi đề nghị đổi lịch xem ${booking.property_label}` +
                  (booking.proposed_start_at && booking.proposed_end_at
                    ? ` sang ${formatTimeRange(booking.proposed_start_at, booking.proposed_end_at)}`
                    : "") +
                  ". Lịch cũ vẫn giữ cho tới khi chủ căn đồng ý; mình sẽ báo bạn ngay khi có phản hồi.",
            trackBookingId: booking.id,
          }
        : {
            role: "assistant",
            text:
              `Đã gửi yêu cầu xem nhà tới chủ căn — mã Deal ${booking.deal_code}. ` +
              "Lịch chỉ có hiệu lực khi chủ căn xác nhận; mình sẽ báo bạn ngay trong khung chat này.",
            bookings: [booking],
          },
    );
  }

  // Links into the chat: a home (/buyer/properties/:id[/schedule]), my viewings, one viewing's status
  const handled = useRef("");
  useEffect(() => {
    const key = searchParams.toString();
    if (!key) {
      handled.current = "";
      return;
    }
    if (handled.current === key) return;
    handled.current = key;
    const id = Number(searchParams.get("property"));
    if (id) {
      openProperty(id);
      if (searchParams.get("schedule")) openSchedule({ id, unit_code: "" });
    }
    const bookingId = Number(searchParams.get("booking"));
    if (bookingId) openStatus(bookingId);
    if (searchParams.get("bookings")) openBookings();
    setSearchParams({}, { replace: true });
  }, [searchParams]);

  // Keeps the reply being typed out in view (instant: smooth scrolling on every frame would lag behind)
  const scrollToEnd = useCallback(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, []);

  const lastId = conversation.messages[conversation.messages.length - 1]?.id;
  useEffect(() => {
    if (skipScroll.current) {
      skipScroll.current = false;
      return;
    }
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lastId, conversation.messages.length, send.isPending]);


  function submit(text: string) {
    const message = text.trim();
    if (!message || busy) return;
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

  // Opening cards counts as starting too: the opening suggestions are no longer needed
  const started = conversation.messages.length > 1;
  // Waiting for the assistant, or its reply is still being typed out
  const busy = send.isPending || live !== null;
  // Guests see the sign-up prompt under the latest reply that needs an account
  let signupAt = -1;
  if (userId === null)
    conversation.messages.forEach((m, i) => m.needsAccount && (signupAt = i));
  const latest =
    [...conversation.messages].reverse().find((m) => m.recommendations?.length)
      ?.recommendations ?? [];
  const hasResults = latest.length > 0;

  return (
    // Just the chat until the assistant has found homes; then the needs + matching homes panel opens beside it
    <div className={hasResults ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]" : "mx-auto w-full max-w-4xl"}>
      <section
        className="card flex h-[calc(100dvh-12rem)] min-h-[28rem] flex-col overflow-hidden shadow-sm"
        aria-label="Chat AI"
      >
        <header className="flex items-center gap-3 border-b border-line px-5 py-4">
          <AiBot className="size-11" animated thinking={send.isPending} />
          <div className="min-w-0 flex-1">
            <h1 className="font-semibold">Trợ lý AI</h1>
            <p className="text-xs text-muted">
              Trợ lý tìm nhà Vinhomes
              {userId === null && " · Bạn đang trò chuyện với tư cách khách"}
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
                  disabled={!started || busy}
                  onClick={restart}
                >
                  Cuộc trò chuyện mới
                </button>
                <button
                  type="button"
                  className="block w-full px-4 py-2 text-left text-sm hover:bg-slate-50"
                  onClick={openBookings}
                >
                  Lịch xem của tôi
                </button>
              </div>
            )}
          </div>
        </header>

        <div
          className="flex-1 space-y-5 overflow-y-auto bg-slate-50/60 p-5"
          aria-live="polite"
        >
          {conversation.messages.map((m, i) => (
            <MessageView
              key={m.id ?? i}
              anchor={`msg-${i}`}
              message={m}
              onPickTime={
                i === conversation.messages.length - 1 && !busy
                  ? (iso) =>
                      submit(
                        `Tôi chọn xem lúc ${timeOf(iso)} ngày ${dateOf(iso)}`,
                      )
                  : undefined
              }
              onReply={busy ? undefined : submit}
              onOpenProperty={openProperty}
              onBook={openSchedule}
              onScheduled={onScheduled}
              onTrack={openStatus}
              onReschedule={openReschedule}
              onBookingChanged={(b) => markKnown([b])}
              onBack={() => goBack(i)}
              signup={
                i === signupAt ? (
                  <div className="max-w-md">
                    <GuestSignup
                      onDone={(u) => onSignedUp(u, m.pendingViewing)}
                    />
                  </div>
                ) : undefined
              }
            />
          ))}
          {sendPending.isPending && (
            <p className="pl-12 text-sm text-muted">
              Đang gửi yêu cầu xem nhà...
            </p>
          )}
          {live &&
            (live.text ? (
              <div className="flex items-start gap-3">
                <AgentAvatar thinking />
                <StreamingText
                  text={live.text}
                  onGrow={scrollToEnd}
                  onCaughtUp={live.final ? () => finishTurn(live.final!) : undefined}
                />
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <AgentAvatar thinking />
                <p className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-line">
                  <Dot delay="0ms" />
                  <Dot delay="150ms" />
                  <Dot delay="300ms" />
                  {live.status ? (
                    <span className="ml-2 text-xs text-muted">{live.status}</span>
                  ) : (
                    <span className="sr-only">Trợ lý đang trả lời</span>
                  )}
                </p>
              </div>
            ))}
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

        <form
          onSubmit={onSubmit}
          className="flex items-center gap-2 border-t border-line bg-white p-3"
        >
          <label htmlFor="chat-input" className="sr-only">
            Tin nhắn
          </label>
          <input
            id="chat-input"
            ref={inputRef}
            className="input rounded-xl py-2.5"
            placeholder={
              started ? "Nhập thêm yêu cầu..." : "Nhập nhu cầu của bạn..."
            }
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
            disabled={!input.trim() || busy}
          >
            <SendIcon className="size-5" />
          </button>
        </form>
      </section>

      {hasResults && <ResultsPanel recommendations={latest} onOpen={openProperty} />}
    </div>
  );
}

/**
 * The reply being written. The model sends text in bursts; it is typed out at an even pace (faster when
 * far behind) so it reads like writing. `onGrow` keeps it in view (instant scroll: smooth would lag behind).
 */
function StreamingText({
  text,
  onGrow,
  onCaughtUp,
}: {
  text: string;
  onGrow: () => void;
  /** Set once the whole reply has arrived: called when the typing-out reaches its end */
  onCaughtUp?: () => void;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (shown >= text.length) return;
    const id = requestAnimationFrame(() => setShown((n) => Math.min(text.length, n + Math.max(1, Math.ceil((text.length - n) / 12)))));
    return () => cancelAnimationFrame(id);
  }, [shown, text]);
  useEffect(() => {
    onGrow();
  }, [onGrow, shown]);
  useEffect(() => {
    if (onCaughtUp && shown >= text.length) onCaughtUp();
  }, [onCaughtUp, shown, text.length]);
  return (
    <p className="w-fit max-w-[90%] whitespace-pre-line rounded-2xl rounded-tl-sm bg-white px-4 py-2.5 text-sm shadow-sm ring-1 ring-line">
      <RichText text={text.slice(0, shown)} />
      <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-brand-500" aria-hidden="true" />
    </p>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="size-1.5 animate-bounce rounded-full bg-brand-500"
      style={{ animationDelay: delay }}
    />
  );
}

function AgentAvatar({ thinking = false }: { thinking?: boolean }) {
  return <AiBot thinking={thinking} />;
}

function MessageView({
  anchor,
  message: m,
  onPickTime,
  onReply,
  onOpenProperty,
  onBook,
  onScheduled,
  onTrack,
  onReschedule,
  onBookingChanged,
  onBack,
  signup,
}: {
  anchor: string;
  message: Message;
  onPickTime?: (iso: string) => void;
  onReply?: (text: string) => void;
  onOpenProperty: (id: number, code?: string) => void;
  onBook: (p: Property) => void;
  onScheduled: (b: Booking, rescheduled: boolean) => void;
  onTrack: (bookingId: number) => void;
  onReschedule: (b: Booking) => void;
  onBookingChanged: (b: Booking) => void;
  onBack: () => void;
  signup?: ReactNode;
}) {
  const times = m.viewingTimes;
  const options = times
    ? times.proposals.length > 0
      ? times.proposals
      : (times.alternatives ?? [])
    : [];
  const criteria = criteriaOf(m.recommendations ?? []);

  if (m.card) {
    const card = m.card;
    return (
      <div id={anchor} className="flex scroll-mt-4 items-start gap-3">
        <AgentAvatar />
        <div className="min-w-0 flex-1">
          {card.kind === "property" && (
            <PropertyDetailCard
              propertyId={card.propertyId}
              onBook={onBook}
              onBack={onBack}
            />
          )}
          {card.kind === "schedule" &&
            (card.done ? (
              <p className="w-fit rounded-2xl rounded-tl-sm bg-white px-4 py-2.5 text-sm text-muted shadow-sm ring-1 ring-line">
                {card.reschedule
                  ? "Đã gửi đề nghị đổi giờ — xem tin nhắn bên dưới."
                  : "Đã gửi yêu cầu xem căn này — xem thẻ Deal bên dưới."}
              </p>
            ) : (
              <ViewingScheduler
                propertyId={card.propertyId}
                reschedule={card.reschedule}
                onBooked={(b) => onScheduled(b, !!card.reschedule)}
                onBack={onBack}
              />
            ))}
          {card.kind === "status" && (
            <BookingStatusCard
              bookingId={card.bookingId}
              onBack={onBack}
              onReschedule={onReschedule}
              onViewProperty={(id) => onOpenProperty(id)}
              onChanged={onBookingChanged}
            />
          )}
          {card.kind === "bookings" && (
            <BookingsListCard onBack={onBack} onOpenStatus={onTrack} />
          )}
        </div>
      </div>
    );
  }

  if (m.role === "user") {
    return (
      <div id={anchor} className="flex scroll-mt-4 justify-end">
        <p className="max-w-[80%] whitespace-pre-line rounded-2xl rounded-tr-sm bg-brand-100 px-4 py-2.5 text-sm text-ink">
          {m.text}
        </p>
      </div>
    );
  }

  return (
    <div id={anchor} className="flex scroll-mt-4 items-start gap-3">
      <AgentAvatar />
      <div className="min-w-0 flex-1 space-y-3">
        {m.text && (
          <p
            className={`w-fit max-w-[90%] whitespace-pre-line rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm ${
              m.role === "error"
                ? "border border-red-200 bg-red-50 text-red-800"
                : "bg-white shadow-sm ring-1 ring-line"
            }`}
          >
            <RichText text={m.text} />
          </p>
        )}

        {criteria.length > 0 && (
          <dl className="grid max-w-lg grid-cols-2 gap-2 sm:grid-cols-3">
            {criteria.map((c) => (
              <div
                key={c.label}
                className="rounded-xl border border-line bg-white px-3 py-2"
              >
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
                <ResultRow rec={r} onOpen={onOpenProperty} />
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
          <div
            key={b.id}
            className="card w-full max-w-md space-y-1 p-4 text-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">Deal {b.deal_code}</span>
              <BookingBadge status={b.status} />
            </div>
            <p className="text-muted">{b.property_label}</p>
            <p>{formatTimeRange(b.start_at, b.end_at)}</p>
            <button
              type="button"
              className="font-medium text-brand-700 hover:underline"
              onClick={() => onTrack(b.id)}
            >
              Theo dõi trạng thái
            </button>
          </div>
        ))}

        {(!!m.propertyIds?.length ||
          !!m.trackBookingId ||
          !!m.replies?.length) && (
          <div className="flex flex-wrap gap-1.5">
            {m.propertyIds?.map((id) => (
              <PropertyChip key={id} propertyId={id} onOpen={onOpenProperty} />
            ))}
            {m.trackBookingId && (
              <button
                type="button"
                className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 hover:border-brand-500"
                onClick={() => onTrack(m.trackBookingId!)}
              >
                Theo dõi trạng thái
              </button>
            )}
            {m.replies?.map((r) => (
              <button
                key={r}
                type="button"
                disabled={!onReply}
                className="rounded-full border border-line bg-white px-3 py-1.5 text-xs text-muted hover:border-brand-500 hover:text-brand-700 disabled:opacity-50"
                onClick={() => onReply?.(r)}
              >
                {r}
              </button>
            ))}
          </div>
        )}

        {signup}
      </div>
    </div>
  );
}

/** A home the agent suggested in a follow-up: its code, opening its details card. */
function PropertyChip({
  propertyId,
  onOpen,
}: {
  propertyId: number;
  onOpen: (id: number, code?: string) => void;
}) {
  const property = useProperty(propertyId);
  const code = property.data?.unit_code;
  return (
    <button
      type="button"
      className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 hover:border-brand-500"
      onClick={() => onOpen(propertyId, code)}
    >
      Xem căn {code ?? `#${propertyId}`}
      {property.data && ` · ${formatVnd(property.data.price_vnd)}`}
    </button>
  );
}

/** Wireframe 1.3: needs as chips + the matching properties (shown once there are some). */
function ResultsPanel({
  recommendations,
  onOpen,
}: {
  recommendations: Recommendation[];
  onOpen: (id: number, code?: string) => void;
}) {
  const criteria = criteriaOf(recommendations);
  return (
    <aside
      className="card hidden h-[calc(100dvh-12rem)] min-h-[28rem] animate-rise-in flex-col overflow-hidden shadow-sm lg:flex"
      aria-label="Kết quả đề xuất"
    >
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-sm font-semibold">Nhu cầu của bạn</h2>
        {criteria.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {criteria.map((c) => (
              <li
                key={c.label}
                className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-ink"
                title={c.label}
              >
                {c.value}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-muted">
            Trợ lý sẽ tóm tắt tiêu chí sau khi hiểu nhu cầu của bạn.
          </p>
        )}
      </div>
      <p className="border-b border-line px-5 py-2.5 text-sm font-medium text-brand-600">
        <span className="border-b-2 border-brand-600 pb-2.5">
          Căn phù hợp ({recommendations.length})
        </span>
      </p>
      <div className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-3">
          {recommendations.map((r) => (
            <li key={r.property.id}>
              <ResultRow rec={r} onOpen={onOpen} />
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function ResultRow({
  rec,
  onOpen,
}: {
  rec: Recommendation;
  onOpen: (id: number, code?: string) => void;
}) {
  const p = rec.property;
  const scored = rec.matched.length + rec.unmatched.length > 0;
  return (
    <article className="flex gap-3 rounded-xl border border-line bg-white p-2.5">
      <PropertyImage
        src={imagesOf(p)[0]?.url}
        alt={`Căn ${p.unit_code}`}
        className="size-20 shrink-0 rounded-lg sm:h-24 sm:w-28"
      />
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
          <button
            type="button"
            onClick={() => onOpen(p.id, p.unit_code)}
            className="btn btn-sm border border-brand-600 text-brand-600 hover:bg-brand-50"
          >
            Xem chi tiết
          </button>
        </div>
      </div>
    </article>
  );
}
