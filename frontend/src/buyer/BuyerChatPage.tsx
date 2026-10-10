import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useNavigate, useSearchParams } from "react-router";

import { api, ApiError, call, errorMessage, streamChat } from "../api/client";
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
  displayName,
  formatTimeRange,
  formatVnd,
  timeOf,
  VIEW,
} from "../lib/format";
import { useBooking } from "./BookingStatusCard";
import { useJumpFlash } from "../lib/jump";
import { CHAT_EVENTS } from "../lib/notifications";
import { chatStorageKey } from "./guest";
import { GuestSignup } from "./GuestSignup";
import { BuildingIcon, PlusIcon, SendIcon, SparkleIcon, UserIcon } from "./icons";
import { AiBot } from "./AiBot";
import { HomeCard, HomeDetail, ResultsList } from "./HomeResults";
import { PropertyDetailCard, useProperty } from "./PropertyDetailCard";
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
    };

// A home's details or its viewing-time picker: shown in a column left of the chat, not inside it,
// so the whole card fits without scrolling the conversation
type Panel =
  | { kind: "property"; propertyId: number }
  | { kind: "schedule"; propertyId: number; reschedule?: Booking };

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
  // The notification this message came from (opening it from the bell jumps here)
  noteId?: number;
}

interface Conversation {
  id: string;
  messages: Message[];
  // Agent notifications already posted, and when this chat started (older ones are not replayed)
  seenNotes?: number[];
  since?: string;
}

// Posted in the chat as the assistant's own messages. VIEWING_SUPERSEDED: the owner received someone else at the
// time this buyer asked for, so the assistant offers other times
// The assistant's own messages that arrive as notifications (see lib/notifications)
const AGENT_EVENTS = CHAT_EVENTS;

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

// Ways to refine a search, offered under the latest list of homes
/** Up to three refinements that fit these results: only criteria the buyer has not set, views these homes have. */
function refinementsFor(recs: Recommendation[]): string[] {
  const asked = new Set(recs.flatMap((r) => [...r.matched, ...r.unmatched].map((c) => c.criterion)));
  const out = ["Rẻ hơn một chút"];
  if (!asked.has("view")) {
    const view = (["LAKE", "PARK", "RIVER", "POOL"] as const).find((v) => recs.some((r) => r.property.view === v));
    if (view) out.push(`Ưu tiên view ${VIEW[view].toLowerCase()}`);
  }
  if (!asked.has("floor")) out.push("Tầng cao hơn");
  if (out.length < 3 && !asked.has("area")) out.push("Diện tích rộng hơn");
  if (out.length < 3 && !asked.has("direction")) out.push("Hướng Đông Nam");
  return out.slice(0, 3);
}

const SUGGESTIONS = [
  { icon: BuildingIcon, title: "Theo dự án & ngân sách", text: "Tôi cần căn 2 phòng ngủ ở Ocean Park, dưới 3,5 tỷ" },
  { icon: UserIcon, title: "Cho gia đình", text: "Gia đình 4 người, thích view hồ, hướng Đông Nam" },
  { icon: SparkleIcon, title: "Để đầu tư", text: "Tìm căn studio để cho thuê" },
];

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

// Same voice as the assistant's replies: it says "em" and calls the buyer "anh/chị"
function greeting(name: string | null): Message {
  return {
    role: "assistant",
    text:
      `Em chào anh/chị${name ? ` ${name}` : ""}! Anh/chị đang tìm căn Vinhomes như thế nào? ` +
      "Anh/chị cứ mô tả tự nhiên: dự án, ngân sách, số phòng ngủ, tầng, view, mục đích mua...",
  };
}

function fresh(name: string | null): Conversation {
  return {
    id: newId(),
    messages: [greeting(name)],
    since: new Date().toISOString(),
  };
}

// Kept per tab so opening a recommended property and coming back does not lose the chat.
// userId null = guest (a new buyer without an account yet).
function loadConversation(userId: number | null, name: string | null): Conversation {
  try {
    const raw = sessionStorage.getItem(chatStorageKey(userId));
    if (raw) {
      const saved = JSON.parse(raw) as Conversation;
      return {
        since: new Date().toISOString(),
        ...saved,
        // Viewing status cards moved to the "Hoạt động" page
        messages: saved.messages.filter((m) => !m.card || m.card.kind === "property" || m.card.kind === "schedule"),
      };
    }
  } catch {
    // Storage blocked or corrupted: start over
  }
  return fresh(name);
}

// The question being sent, kept until it is answered: if the session expires meanwhile (the buyer is sent to sign
// in), it goes back in the box afterwards instead of being lost
const DRAFT_KEY = "bookingbot.chat.draft";

function readDraft(): string {
  try {
    return sessionStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

function keepDraft(message: string | null) {
  try {
    if (message) sessionStorage.setItem(DRAFT_KEY, message);
    else sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    // Storage blocked: an unanswered question is not kept
  }
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
  const navigate = useNavigate();
  const userId = user?.role === "CUSTOMER" ? user.id : null;
  const name = userId !== null ? displayName(user!.full_name) : null;
  const [draft] = useState(readDraft);
  // Back in the box now; dropped from storage once shown (not while rendering: React may render twice)
  useEffect(() => {
    if (draft) keepDraft(null);
  }, [draft]);
  const [conversation, setConversation] = useState<Conversation>(() => {
    const saved = loadConversation(userId, name);
    // The unanswered question goes back in the box rather than staying in the chat without a reply
    const last = saved.messages[saved.messages.length - 1];
    return draft && last?.role === "user" && last.text === draft
      ? { ...saved, messages: saved.messages.slice(0, -1) }
      : saved;
  });
  const [input, setInput] = useState(draft);
  const [panel, setPanel] = useState<Panel | null>(null);
  // "Cuộc trò chuyện mới" asks once before clearing the chat
  const [confirmRestart, setConfirmRestart] = useState(false);
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

  // Agent follow-ups and new matching homes (sent while the buyer was away) arrive as agent messages
  const notes = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => call(api.GET("/api/v1/notifications")),
    enabled: userId !== null,
    refetchInterval: 30_000,
  });
  // Opened from the bell (?note=ID): that message is shown (even if older than this chat) and flashes
  const openedNote = Number(searchParams.get("note")) || null;
  const noteFlash = useJumpFlash(true);
  useEffect(() => {
    const list = notes.data;
    if (!list) return;
    setConversation((c) => {
      const seen = new Set(c.seenNotes ?? []);
      const since = c.since ? Date.parse(c.since) : 0;
      const shown = new Set(c.messages.map((m) => m.noteId));
      const unseen = list
        .filter(
          (n) =>
            AGENT_EVENTS.has(n.event_type) &&
            ((!seen.has(n.id) && n.sent_at && Date.parse(n.sent_at) > since) ||
              (n.id === openedNote && !shown.has(n.id))),
        )
        .reverse();
      if (unseen.length === 0) return c;
      const news: Message[] = unseen.map((n) => {
        const payload = (n.payload ?? {}) as {
          property_ids?: number[];
          property_id?: number;
          unit_code?: string;
          suggested_starts?: string[];
        };
        return {
          id: newId(),
          noteId: n.id,
          role: "assistant",
          text: `**${n.title}**\n${n.body}`,
          propertyIds:
            payload.property_ids ??
            (payload.property_id ? [payload.property_id] : []),
          trackBookingId: n.booking_id ?? undefined,
          replies:
            (n.event_type === "VIEWING_SUPERSEDED" || n.event_type === "VIEWING_EXPIRED") && payload.unit_code
              ? [`Tìm giờ xem khác cho căn ${payload.unit_code}`, "Tìm căn tương tự"]
              : n.event_type === "VIEWING_TIMES_SUGGESTED" && payload.unit_code
                ? // The owner's own times: picking one asks the assistant to book exactly that
                  (payload.suggested_starts ?? [])
                    .filter((t) => Date.parse(t) > Date.now())
                    .map((t) => `Đặt xem căn ${payload.unit_code} lúc ${timeOf(t)} ngày ${dateOf(t)}`)
                : undefined,
        };
      });
      return {
        ...c,
        seenNotes: [...new Set([...seen, ...unseen.map((n) => n.id)])],
        messages: [...c.messages, ...news],
      };
    });
  }, [notes.data, openedNote]);

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
      keepDraft(null);
      // Let the typing-out finish first (StreamingText calls finishTurn); nothing typed -> show it now
      if (streamed.current) setLive((l) => (l ? { ...l, final: res } : l));
      else finishTurn(res);
    },
    onError: (err) => {
      setLive(null);
      // Signed out (session expired): the buyer is sent to sign in, the question is kept for afterwards
      if (err instanceof ApiError && err.status === 401) return;
      keepDraft(null);
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
      if (res.bookings?.length) queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
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
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
      append({
        role: "assistant",
        text:
          `Đã gửi yêu cầu xem nhà tới chủ căn — mã Deal ${booking.deal_code}. ` +
          "Lịch chỉ có hiệu lực khi chủ căn xác nhận; bạn theo dõi trạng thái trong mục Hoạt động.",
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

  // A home's details and its viewing-time picker open in the side panel; status and the buyer's viewings
  // open as cards in the chat
  function openProperty(id: number, code?: string) {
    setViewing({ id, code });
    setPanel({ kind: "property", propertyId: id });
  }

  function openSchedule(p: Pick<Property, "id" | "unit_code">) {
    setViewing({ id: p.id, code: p.unit_code || undefined });
    setPanel({ kind: "schedule", propertyId: p.id });
  }

  function closePanel() {
    setPanel(null);
    setViewing(null);
  }

  /** A viewing's status, reschedule and QR pass: on the "Hoạt động" page, which a new chat does not clear. */
  function openStatus(bookingId: number) {
    navigate(`/buyer/activity?booking=${bookingId}`);
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
    setPanel(null);
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
                  "Chủ căn đã được báo và vẫn cần xác nhận giờ mới; bạn theo dõi trong mục Hoạt động."
                : `Đã gửi đề nghị đổi lịch xem ${booking.property_label}` +
                  (booking.proposed_start_at && booking.proposed_end_at
                    ? ` sang ${formatTimeRange(booking.proposed_start_at, booking.proposed_end_at)}`
                    : "") +
                  ". Lịch cũ vẫn giữ cho tới khi chủ căn đồng ý; bạn theo dõi trong mục Hoạt động.",
            trackBookingId: booking.id,
          }
        : {
            role: "assistant",
            text:
              `Đã gửi yêu cầu xem nhà tới chủ căn — mã Deal ${booking.deal_code}. ` +
              "Lịch chỉ có hiệu lực khi chủ căn xác nhận; bạn theo dõi trạng thái trong mục Hoạt động (có cả khi bắt đầu cuộc trò chuyện mới).",
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
    if (searchParams.get("home")) closePanel();
    const bookingId = Number(searchParams.get("booking"));
    if (bookingId) {
      openStatus(bookingId);
      return;
    }
    if (searchParams.get("bookings")) {
      navigate("/buyer/activity");
      return;
    }
    // Opened from a notification: keep ?note= so that message is shown and lights up
    if (searchParams.get("note")) return;
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
    keepDraft(message);
    send.mutate(message);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(input);
  }

  function restart() {
    setConfirmRestart(false);
    closePanel();
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
  const needs = criteriaOf(latest);
  const project = needs.find((n) => n.label === "Dự án")?.value;
  // Just the chat at first; the right-hand panel opens once there are homes (or a home is opened)
  const showRight = hasResults || panel !== null;
  const topHome = latest[0]?.property;

  function addNeed() {
    closePanel();
    inputRef.current?.focus();
  }

  const right = panel ? (
    panel.kind === "property" ? (
      <HomeDetail
        key={panel.propertyId}
        propertyId={panel.propertyId}
        rec={latest.find((r) => r.property.id === panel.propertyId)}
        project={project}
        onBack={closePanel}
        onBook={openSchedule}
      />
    ) : (
      <div className="h-full space-y-3 overflow-y-auto px-5 py-5 md:px-7">
        <button
          type="button"
          onClick={() =>
            panel.reschedule ? closePanel() : setPanel({ kind: "property", propertyId: panel.propertyId })
          }
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:underline"
        >
          ← {panel.reschedule ? "Đóng" : "Chi tiết căn"}
        </button>
        <ViewingScheduler
          key={`${panel.propertyId}-${panel.reschedule?.id ?? "new"}`}
          propertyId={panel.propertyId}
          reschedule={panel.reschedule}
          onBooked={(b) => onScheduled(b, !!panel.reschedule)}
        />
      </div>
    )
  ) : hasResults ? (
    <ResultsList
      recommendations={latest}
      needs={needs}
      onOpen={openProperty}
      onRemoveNeed={busy ? undefined : (n) => submit(`Bỏ tiêu chí ${n.label.toLowerCase()} (${n.value}) và tìm lại giúp tôi`)}
      onAddNeed={addNeed}
    />
  ) : null;

  return (
    <div
      className={
        showRight
          ? "grid gap-5 lg:grid-cols-[minmax(22rem,34rem)_minmax(0,1fr)]"
          : "mx-auto w-full max-w-3xl"
      }
    >
      <section
        className="flex h-[calc(100dvh-7rem)] min-h-[30rem] flex-col overflow-hidden rounded-[28px] bg-gradient-to-b from-[#f2f6fe] to-[#eaf0fb] shadow-xl shadow-slate-900/5 ring-1 ring-line"
        aria-label="Chat AI"
      >
        <header className="flex items-center gap-3 border-b border-line/70 bg-white/80 px-5 py-3.5 backdrop-blur">
          <span className="relative">
            <AiBot className="size-12" animated thinking={send.isPending} />
            <span
              className="absolute bottom-0 right-0 size-3.5 rounded-full bg-emerald-500 ring-[3px] ring-white"
              aria-hidden="true"
            />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-2 whitespace-nowrap font-display text-base font-bold leading-tight sm:text-lg">
              Trợ lý BookingBot
              {userId === null && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 font-sans text-[11px] font-semibold text-amber-800">
                  Khách
                </span>
              )}
            </h1>
            <p className="truncate text-xs text-muted">
              {busy ? (
                <span className="font-medium text-brand-700">Đang tìm và trả lời…</span>
              ) : (
                <>
                  <span className="text-emerald-600">●</span> Sẵn sàng · chỉ gợi ý căn Vinhomes đã xác thực
                </>
              )}
            </p>
          </div>
          {confirmRestart ? (
            <div className="flex items-center gap-2 text-sm" role="group" aria-label="Xác nhận cuộc trò chuyện mới">
              <span className="hidden text-muted sm:inline">Xóa cuộc trò chuyện này?</span>
              <button type="button" className="rounded-full bg-brand-600 px-3 py-1.5 font-semibold text-white" onClick={restart}>
                Bắt đầu mới
              </button>
              <button type="button" className="rounded-full px-3 py-1.5 font-semibold hover:bg-sand" onClick={() => setConfirmRestart(false)}>
                Hủy
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-2 text-sm sm:px-3.5 font-semibold text-ink shadow-sm transition hover:border-brand-500 hover:text-brand-700 disabled:opacity-40"
              disabled={!started || busy}
              onClick={() => setConfirmRestart(true)}
            >
              <PlusIcon className="size-4" />
              <span className="sr-only sm:not-sr-only">Cuộc mới</span>
            </button>
          )}
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5" aria-live="polite">
          {conversation.messages.map((m, i) => (
            <div key={m.id ?? i} ref={m.noteId !== undefined && m.noteId === openedNote ? noteFlash : undefined} className="rounded-3xl">
            <MessageView
              anchor={`msg-${i}`}
              message={m}
              onPickTime={
                i === conversation.messages.length - 1 && !busy
                  ? (iso) => submit(`Tôi chọn xem lúc ${timeOf(iso)} ngày ${dateOf(iso)}`)
                  : undefined
              }
              // Quick replies of earlier turns no longer apply
              onReply={busy || i !== conversation.messages.length - 1 ? undefined : submit}
              onOpenProperty={openProperty}
              onBook={openSchedule}
              onScheduled={onScheduled}
              onTrack={openStatus}
              onBack={() => goBack(i)}
              followUps={
                // Under the latest list of homes, while it is the last message: open the best one, or refine
                m.recommendations?.length &&
                m.recommendations === latest &&
                topHome &&
                i === conversation.messages.length - 1 ? (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="rounded-full bg-brand-600 px-4 py-1.5 font-display text-sm font-bold text-canvas hover:bg-brand-700"
                      onClick={() => openProperty(topHome.id, topHome.unit_code)}
                    >
                      Xem {topHome.unit_code}
                    </button>
                    {refinementsFor(latest).map((r) => (
                      <button
                        key={r}
                        type="button"
                        disabled={busy}
                        className="rounded-full border border-line bg-white px-3.5 py-1.5 text-[13px] font-semibold shadow-sm hover:border-brand-500 hover:text-brand-700 disabled:opacity-50"
                        onClick={() => submit(r)}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                ) : undefined
              }
              signup={
                i === signupAt ? (
                  <div className="max-w-md">
                    <GuestSignup onDone={(u) => onSignedUp(u, m.pendingViewing)} />
                  </div>
                ) : undefined
              }
            />
            </div>
          ))}
          {sendPending.isPending && <p className="pl-12 text-sm text-muted">Đang gửi yêu cầu xem nhà...</p>}
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
                <p className="flex items-center gap-1 rounded-3xl rounded-tl-md bg-white shadow-sm ring-1 ring-line px-4 py-3.5">
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
          <div className="px-5 pb-2">
            <p className="mb-2.5 text-xs font-bold uppercase tracking-[0.14em] text-muted">Gợi ý để bắt đầu</p>
            <div className="grid gap-2.5 sm:grid-cols-3">
              {SUGGESTIONS.map(({ icon: Icon, title, text }) => (
                <button
                  key={text}
                  type="button"
                  className="group flex flex-col items-start rounded-2xl bg-white p-3.5 text-left shadow-sm ring-1 ring-line transition hover:-translate-y-0.5 hover:shadow-md hover:ring-brand-300"
                  onClick={() => submit(text)}
                >
                  <span className="flex items-center gap-2 text-xs font-bold text-brand-700">
                    <span className="grid size-7 place-items-center rounded-lg bg-brand-50">
                      <Icon className="size-4" />
                    </span>
                    {title}
                  </span>
                  <span className="mt-2 block text-[13px] leading-snug text-ink/80 group-hover:text-ink">{text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <form onSubmit={onSubmit} className="px-4 pb-3 pt-2">
          <div className="flex items-center gap-2 rounded-[22px] bg-white p-1.5 pl-5 shadow-lg shadow-slate-900/5 ring-1 ring-line transition focus-within:ring-2 focus-within:ring-brand-500">
            <label htmlFor="chat-input" className="sr-only">
              Tin nhắn
            </label>
            <input
              id="chat-input"
              ref={inputRef}
              className="min-w-0 flex-1 bg-transparent py-2.5 text-[15px] outline-none placeholder:text-muted"
              placeholder={started ? "Thêm yêu cầu, ví dụ: tầng cao, view hồ..." : "Mô tả căn bạn đang tìm..."}
              maxLength={5000}
              autoFocus
              autoComplete="off"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              type="submit"
              className="grid size-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#1463ff] to-[#5b3df5] text-white shadow-md shadow-brand-600/25 transition hover:brightness-110 disabled:opacity-40 disabled:shadow-none"
              aria-label="Gửi"
              disabled={!input.trim() || busy}
            >
              <SendIcon className="size-5" />
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-muted">
            Trợ lý chỉ gợi ý căn có trong hệ thống · Số điện thoại của bạn luôn được ẩn với chủ căn
          </p>
        </form>
      </section>

      {right && (
        // Desktop: the panel beside the chat. Phones/tablets: home details / booking fill the screen below the
        // site header (4.5rem, see BuyerLayout), so the navigation stays; the list of homes is shown in the chat.
        <section
          className={`animate-rise-in overflow-hidden bg-paper lg:static lg:block lg:h-[calc(100dvh-7rem)] lg:min-h-[30rem] lg:rounded-[28px] lg:shadow-xl lg:shadow-slate-900/5 lg:ring-1 lg:ring-line ${
            panel ? "fixed inset-x-0 bottom-0 top-[4.5rem] z-30" : "hidden"
          }`}
          aria-label={panel ? (panel.kind === "property" ? "Chi tiết căn" : "Chọn lịch xem nhà") : "Kết quả đề xuất"}
        >
          {right}
        </section>
      )}
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
    <p className="w-fit max-w-[92%] whitespace-pre-line rounded-3xl rounded-tl-md bg-white shadow-sm ring-1 ring-line px-4 py-3 text-[15px] leading-relaxed">
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
  onBack,
  followUps,
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
  onBack: () => void;
  followUps?: ReactNode;
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
        </div>
      </div>
    );
  }

  if (m.role === "user") {
    return (
      <div id={anchor} className="flex scroll-mt-4 justify-end">
        <p className="max-w-[85%] whitespace-pre-line rounded-3xl rounded-tr-md bg-gradient-to-br from-[#1463ff] to-[#5b3df5] text-white shadow-md shadow-brand-600/20 px-4 py-2.5 text-[15px]">
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
            className={`w-fit max-w-[92%] whitespace-pre-line rounded-3xl rounded-tl-md px-4 py-3 text-[15px] leading-relaxed ${
              m.role === "error" ? "border border-red-200 bg-red-50 text-red-800" : "bg-white shadow-sm ring-1 ring-line"
            }`}
          >
            <RichText text={m.text} />
          </p>
        )}

        {criteria.length > 0 && (
          <dl className="grid max-w-lg grid-cols-2 gap-2 sm:grid-cols-3 lg:hidden">
            {criteria.map((c) => (
              <div
                key={c.label}
                className="rounded-xl bg-leaf px-3 py-2"
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
                <HomeCard rec={r} onOpen={onOpenProperty} />
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
                className="rounded-full border border-line bg-white px-3.5 py-1.5 text-[13px] font-semibold shadow-sm hover:border-brand-500 hover:text-brand-700 disabled:opacity-50"
              >
                {formatTimeRange(o.start_at, o.end_at)}
              </button>
            ))}
          </div>
        )}

        {m.bookings?.map((b) => <ChatBookingCard key={b.id} booking={b} onTrack={onTrack} />)}

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
                Xem trong Hoạt động →
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

        {followUps}
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

/** A viewing request the assistant made, shown as it stands now (not as it was when the message was written). */
function ChatBookingCard({ booking, onTrack }: { booking: Booking; onTrack: (id: number) => void }) {
  const b = useBooking(booking.id).data ?? booking;
  return (
    <div className="card w-full max-w-md space-y-1 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">Deal {b.deal_code}</span>
        <BookingBadge status={b.status} />
      </div>
      <p className="text-muted">{b.property_label}</p>
      <p>{formatTimeRange(b.start_at, b.end_at)}</p>
      <button type="button" className="font-medium text-brand-700 hover:underline" onClick={() => onTrack(b.id)}>
        Theo dõi trong Hoạt động →
      </button>
    </div>
  );
}
