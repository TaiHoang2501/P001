import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, call } from "../api/client";
import type { components } from "../api/schema";
import type { Booking } from "../api/types";
import { BookingBadge, ErrorBox, Spinner } from "../components/ui";
import { formatDateTime, formatTimeRange, TIMEZONE } from "../lib/format";
import { useJumpFlash } from "../lib/jump";
import { needsBuyerAfterViewing } from "./AfterViewing";
import { BookingStatusCard } from "./BookingStatusCard";
import { CalendarIcon, CheckCircleIcon, ClockIcon } from "./icons";
import { ViewingScheduler } from "./ViewingScheduler";

type Activity = components["schemas"]["ActivityOut"];
type Kind = Activity["kind"];

const PENDING = new Set<Booking["status"]>(["REQUESTED", "RESCHEDULE_REQUESTED"]);

/** How each event reads, and its colour: blue = the buyer asked, green = good news, red/amber = a no. */
const EVENT: Record<Kind, { title: (a: Activity) => string; tone: "ask" | "good" | "bad" | "warn" | "done" }> = {
  REQUESTED: { title: () => "Bạn đã gửi yêu cầu xem nhà", tone: "ask" },
  TIME_CHANGED: { title: () => "Bạn đã đổi giờ trong yêu cầu xem", tone: "ask" },
  RESCHEDULE_REQUESTED: { title: () => "Bạn đề nghị đổi lịch xem", tone: "ask" },
  CONFIRMED: { title: () => "Chủ căn đã xác nhận lịch xem", tone: "good" },
  REJECTED: { title: () => "Chủ căn từ chối lịch xem", tone: "bad" },
  RESCHEDULE_APPROVED: { title: () => "Chủ căn đồng ý đổi giờ", tone: "good" },
  RESCHEDULE_DECLINED: {
    title: (a) =>
      a.by === "BOOKINGBOT"
        ? "Giờ mới không còn trống (chủ căn đã nhận lịch khác), lịch cũ giữ nguyên"
        : "Chủ căn không đồng ý đổi giờ, lịch cũ giữ nguyên",
    tone: "warn",
  },
  CANCELLED: {
    title: (a) =>
      a.by === "BUYER" ? "Bạn đã hủy lịch xem" : a.by === "OWNER" ? "Chủ căn đã hủy lịch xem" : "BookingBot đã hủy lịch xem",
    tone: "bad",
  },
  COMPLETED: {
    title: (a) => (a.by === "BOOKINGBOT" ? "Chủ đầu tư xác nhận buổi xem đã diễn ra" : "Buổi xem đã hoàn tất"),
    tone: "done",
  },
  NO_SHOW: {
    title: (a) => (a.by === "BOOKINGBOT" ? "Chủ đầu tư xác định bạn không đến" : "Chủ căn ghi nhận bạn không đến"),
    tone: "warn",
  },
  OWNER_ABSENT: { title: () => "Chủ căn không có mặt ở buổi xem (Chủ đầu tư đã xác minh)", tone: "bad" },
  UNREPORTED: { title: () => "Không ai ghi nhận kết quả buổi xem, lịch tự đóng", tone: "done" },
  EXPIRED: { title: () => "Chủ căn chưa trả lời trước giờ xem, yêu cầu tự hết hạn", tone: "warn" },
  RESCHEDULE_LAPSED: { title: () => "Giờ mới bạn xin đã qua mà chủ căn chưa đồng ý; lịch giữ giờ cũ", tone: "warn" },
  INTERESTED: { title: () => "Bạn báo quan tâm căn này", tone: "good" },
  NOT_SUITABLE: { title: () => "Bạn thấy căn chưa phù hợp", tone: "done" },
  DISPUTED: { title: () => "Bạn gửi phản hồi về kết quả buổi xem cho Chủ đầu tư", tone: "ask" },
  SUPERSEDED: { title: () => "Chủ căn đã nhận một lịch xem khác vào giờ này", tone: "bad" },
  SOLD: { title: () => "Căn đã được bán, lịch xem đã hủy", tone: "bad" },
};

const TONE = {
  ask: "bg-brand-50 text-brand-700 ring-brand-100",
  good: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  bad: "bg-red-50 text-red-700 ring-red-100",
  warn: "bg-amber-50 text-amber-700 ring-amber-100",
  done: "bg-slate-100 text-slate-700 ring-slate-200",
};

const WHEN_LABEL: Partial<Record<Kind, string>> = {
  REQUESTED: "Giờ xem",
  TIME_CHANGED: "Giờ mới",
  RESCHEDULE_REQUESTED: "Giờ mới đề nghị",
  CONFIRMED: "Giờ xem",
  RESCHEDULE_APPROVED: "Giờ xem mới",
  RESCHEDULE_DECLINED: "Vẫn xem lúc",
  SUPERSEDED: "Giờ bạn đã chọn",
  SOLD: "Giờ xem đã hủy",
};

/**
 * "Hoạt động": the buyer's viewings and everything that happened to them (owner confirmed, declined, changed
 * the time…). Kept on the server, so it survives a new chat; replaces status updates inside the chat.
 */
export function ActivityPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selectedId = Number(params.get("booking")) || null;
  const [reschedule, setReschedule] = useState<Booking | null>(null);

  const activity = useQuery({
    queryKey: ["my-activity"],
    queryFn: () => call(api.GET("/api/v1/bookings/activity")),
    refetchInterval: 30_000,
  });
  const bookings = useQuery({
    queryKey: ["my-bookings"],
    queryFn: () => call(api.GET("/api/v1/bookings")),
    refetchInterval: 30_000,
  });

  const select = (id: number | null) => {
    setReschedule(null);
    setParams(id ? { booking: String(id) } : {}, { replace: true });
  };
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["my-activity"] });
    queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
  };

  // Phones: the viewing opens over the page, so the page behind must not scroll
  useEffect(() => {
    if (!selectedId || window.matchMedia("(min-width: 1024px)").matches) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [selectedId]);

  const now = Date.now();
  const pending = (bookings.data ?? []).filter((b) => PENDING.has(b.status));
  const upcoming = (bookings.data ?? [])
    .filter((b) => b.status === "CONFIRMED" && Date.parse(b.end_at) > now)
    .sort((a, b) => Date.parse(a.start_at) - Date.parse(b.start_at));
  const events = activity.data ?? [];
  // Opened from a notification: the event of that viewing recorded with it (within a minute) lights up in the
  // history; without one (e.g. a reminder) the viewing's row and card do
  const sentAt = params.get("at") ? Date.parse(params.get("at")!) : null;
  const jumpEventId =
    sentAt === null
      ? null
      : (events
          .filter((a) => a.booking_id === selectedId && Math.abs(Date.parse(a.at) - sentAt) <= 60_000)
          .sort((x, y) => Math.abs(Date.parse(x.at) - sentAt) - Math.abs(Date.parse(y.at) - sentAt))[0]?.id ?? null);
  // After the viewing time: something to say (how it went) or to check (what was recorded)
  const after = (bookings.data ?? []).filter(needsBuyerAfterViewing);

  const detail = selectedId && (
    <div className="space-y-3">
      {reschedule ? (
        <ViewingScheduler
          key={reschedule.id}
          propertyId={reschedule.property_id}
          reschedule={reschedule}
          onBack={() => setReschedule(null)}
          onBooked={() => {
            setReschedule(null);
            refresh();
          }}
        />
      ) : (
        <JumpTarget active={jumpEventId === null}>
        <BookingStatusCard
          key={selectedId}
          bookingId={selectedId}
          onBack={() => select(null)}
          onReschedule={setReschedule}
          onViewProperty={(id) => navigate(`/buyer/properties/${id}`)}
          onChanged={(next) => {
            refresh();
            // Booked one of the owner's suggested times: show that new request
            if (next.id !== selectedId) select(next.id);
          }}
        />
        </JumpTarget>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-6xl py-2">
      <header className="mb-6">
        <h1 className="font-display text-3xl font-bold sm:text-4xl">Hoạt động</h1>
        <p className="mt-1 text-muted">
          Lịch xem nhà và mọi phản hồi của chủ căn, được lưu lại kể cả khi bạn bắt đầu cuộc trò chuyện mới.
        </p>
      </header>

      <div className={`grid gap-6 ${selectedId ? "lg:grid-cols-[minmax(0,1fr)_28rem]" : ""}`}>
        <div className="min-w-0 space-y-8">
          {(bookings.isError || activity.isError) && (
            <ErrorBox error={bookings.error ?? activity.error} onRetry={refresh} />
          )}

          <Section
            icon={<ClockIcon className="size-5" />}
            title="Đang chờ chủ căn xác nhận"
            count={pending.length}
            empty={bookings.isPending ? <Spinner /> : "Không có yêu cầu nào đang chờ."}
          >
            {pending.map((b) => (
              <BookingRow key={b.id} booking={b} selected={b.id === selectedId}
                lightUp={jumpEventId === null} onOpen={() => select(b.id)}>
                {b.status === "RESCHEDULE_REQUESTED" && b.proposed_start_at && b.proposed_end_at
                  ? `Đề nghị đổi sang ${formatTimeRange(b.proposed_start_at, b.proposed_end_at)}`
                  : "Chủ căn sẽ trả lời sớm; bạn được báo ngay khi có phản hồi."}
              </BookingRow>
            ))}
          </Section>

          {after.length > 0 && (
            <Section icon={<CheckCircleIcon className="size-5" />} title="Sau buổi xem" count={after.length}>
              {after.map((b) => (
                <BookingRow
                  key={b.id}
                  booking={b}
                  selected={b.id === selectedId}
                lightUp={jumpEventId === null}
                  onOpen={() => select(b.id)}
                  action={b.status === "COMPLETED" ? "Cho biết cảm nhận" : "Xem chi tiết"}
                >
                  {b.status === "COMPLETED"
                    ? "Bạn thấy căn thế nào? Quan tâm thì chủ căn được báo."
                    : b.status === "NO_SHOW"
                      ? "Chủ căn ghi nhận bạn không đến. Thực ra bạn có đến? Mở để phản hồi."
                      : "Buổi xem đã qua, chờ chủ căn ghi nhận kết quả."}
                </BookingRow>
              ))}
            </Section>
          )}

          {upcoming.length > 0 && (
            <Section icon={<CalendarIcon className="size-5" />} title="Lịch xem sắp tới" count={upcoming.length}>
              {upcoming.map((b) => (
                <BookingRow key={b.id} booking={b} selected={b.id === selectedId}
                lightUp={jumpEventId === null} onOpen={() => select(b.id)} action="Mã QR & chi tiết">
                  Đã xác nhận · có mã QR vào cửa
                </BookingRow>
              ))}
            </Section>
          )}

          <section aria-labelledby="history-title">
            <h2 id="history-title" className="mb-3 flex items-center gap-2 font-display text-xl font-bold">
              <CheckCircleIcon className="size-5 text-brand-600" />
              Lịch sử hoạt động
            </h2>
            {activity.isPending && <Spinner />}
            {activity.data && events.length === 0 && (
              <p className="rounded-2xl bg-white p-5 text-sm text-muted ring-1 ring-line">
                Chưa có hoạt động nào. Hãy{" "}
                <Link to="/buyer/chat" className="font-semibold text-brand-700 hover:underline">
                  trò chuyện với Trợ lý AI
                </Link>{" "}
                để tìm căn và đặt lịch xem.
              </p>
            )}
            {groupByDay(events).map(([day, items]) => (
              <div key={day} className="mb-5">
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-muted">{day}</p>
                <ol className="relative space-y-3 border-l-2 border-line pl-6">
                  {items.map((a) => (
                    <EventItem
                      key={a.id}
                      activity={a}
                      jumped={a.id === jumpEventId}
                      selected={a.booking_id === selectedId}
                      onOpen={() => select(a.booking_id)}
                    />
                  ))}
                </ol>
              </div>
            ))}
          </section>
        </div>

        {detail && (
          // Desktop: beside the list. Phones: full screen over it
          <aside
            className="fixed inset-0 z-30 overflow-y-auto bg-canvas p-4 lg:static lg:z-auto lg:overflow-visible lg:bg-transparent lg:p-0"
            aria-label="Chi tiết lịch xem"
          >
            <div className="lg:sticky lg:top-24">{detail}</div>
          </aside>
        )}
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  count,
  empty,
  children,
}: {
  icon: ReactNode;
  title: string;
  count: number;
  empty?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 font-display text-xl font-bold">
        <span className="text-brand-600">{icon}</span>
        {title}
        {count > 0 && (
          <span className="rounded-full bg-brand-600 px-2 py-0.5 font-sans text-xs font-bold text-white">{count}</span>
        )}
      </h2>
      {count === 0 ? (
        <div className="rounded-2xl bg-white p-5 text-sm text-muted ring-1 ring-line">{empty}</div>
      ) : (
        <ul className="space-y-2.5">{children}</ul>
      )}
    </section>
  );
}

function BookingRow({
  booking: b,
  selected,
  lightUp = true,
  onOpen,
  action = "Theo dõi trạng thái",
  children,
}: {
  booking: Booking;
  selected: boolean;
  // Opened from a notification with no event of its own in the history: the row lights up instead
  lightUp?: boolean;
  onOpen: () => void;
  action?: string;
  children: ReactNode;
}) {
  const flash = useJumpFlash(selected && lightUp);
  return (
    <li
      ref={flash}
      className={`flex flex-wrap items-center gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 transition ${
        selected ? "ring-2 ring-brand-500" : "ring-line"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate font-semibold">{b.property_label}</span>
          <BookingBadge status={b.status} />
        </div>
        <p className="mt-0.5 text-sm">
          {formatTimeRange(b.start_at, b.end_at)} · <span className="font-mono text-muted">{b.deal_code}</span>
        </p>
        <p className="mt-0.5 text-xs text-muted">{children}</p>
      </div>
      <button
        type="button"
        onClick={onOpen}
        className="rounded-full bg-brand-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-brand-700"
      >
        {action}
      </button>
    </li>
  );
}

function EventItem({
  activity: a,
  selected,
  jumped,
  onOpen,
}: {
  activity: Activity;
  selected: boolean;
  jumped: boolean;
  onOpen: () => void;
}) {
  // Opened from the notification about this event: it lights up
  const flash = useJumpFlash(jumped);
  const e = EVENT[a.kind];
  const whenLabel = WHEN_LABEL[a.kind];
  // A request the owner has not answered yet: follow it from here
  const stillPending = a.kind === "REQUESTED" || a.kind === "TIME_CHANGED" || a.kind === "RESCHEDULE_REQUESTED";
  const canTrack = stillPending && PENDING.has(a.booking_status);
  return (
    <li ref={flash} className="relative rounded-2xl">
      <span
        aria-hidden="true"
        className={`absolute -left-[33px] top-4 size-4 rounded-full ring-4 ring-canvas ${DOT[e.tone]}`}
      />
      <div
        className={`rounded-2xl bg-white p-4 shadow-sm ring-1 transition ${selected ? "ring-2 ring-brand-500" : "ring-line"}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className={`rounded-full px-2.5 py-1 text-sm font-semibold ring-1 ${TONE[e.tone]}`}>{e.title(a)}</p>
          <time className="text-xs text-muted" dateTime={a.at}>
            {timeOfDay(a.at)}
          </time>
        </div>
        <p className="mt-2 truncate text-sm font-medium">{a.property_label}</p>
        <p className="text-xs text-muted">
          {whenLabel && a.start_at && (
            <>
              {whenLabel}: <span className="font-semibold text-ink">{formatDateTime(a.start_at)}</span> ·{" "}
            </>
          )}
          <span className="font-mono">{a.deal_code}</span>
        </p>
        {a.reason && <p className="mt-2 rounded-xl bg-slate-50 px-3 py-2 text-sm">“{a.reason}”</p>}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {canTrack ? (
            <button
              type="button"
              onClick={onOpen}
              className="rounded-full bg-brand-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-brand-700"
            >
              Theo dõi trạng thái
            </button>
          ) : (
            <button type="button" onClick={onOpen} className="text-xs font-semibold text-brand-700 hover:underline">
              Xem lịch xem →
            </button>
          )}
          <span className="text-xs text-muted">
            Hiện tại: <BookingBadge status={a.booking_status} />
          </span>
        </div>
      </div>
    </li>
  );
}

const DOT = {
  ask: "bg-brand-500",
  good: "bg-emerald-500",
  bad: "bg-red-500",
  warn: "bg-amber-500",
  done: "bg-slate-400",
};

function dayKey(iso: string): string {
  return new Date(iso).toLocaleDateString("vi-VN", { timeZone: TIMEZONE, weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
}

function timeOfDay(iso: string): string {
  return new Date(iso).toLocaleTimeString("vi-VN", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit" });
}

/** Events grouped under "Hôm nay", "Hôm qua" or the date, newest first. */
function groupByDay(events: Activity[]): [string, Activity[]][] {
  const today = dayKey(new Date().toISOString());
  const yesterday = dayKey(new Date(Date.now() - 86_400_000).toISOString());
  const groups = new Map<string, Activity[]>();
  for (const a of events) {
    const key = dayKey(a.at);
    const label = key === today ? "Hôm nay" : key === yesterday ? "Hôm qua" : key;
    groups.set(label, [...(groups.get(label) ?? []), a]);
  }
  return [...groups.entries()];
}

/** The opened viewing's details, lit up when the page was opened from a notification. */
function JumpTarget({ active, children }: { active: boolean; children: ReactNode }) {
  const flash = useJumpFlash(active);
  return (
    <div ref={flash} className="rounded-3xl">
      {children}
    </div>
  );
}
