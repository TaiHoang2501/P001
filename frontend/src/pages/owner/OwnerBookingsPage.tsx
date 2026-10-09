import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import type { Booking } from "../../api/types";
import { ErrorBox, Spinner } from "../../components/ui";
import {
  BOOKING_STATUS,
  formatDateTime,
  formatTimeRange,
  formatVnd,
} from "../../lib/format";
import {
  needsAnswer,
  useOwnerBookings,
  useOwnerOverview,
  useOwnerProperties,
  WAITING,
} from "./ownerData";

// Reasons a seller usually gives; one tap fills the box (the buyer sees it)
const BUSY_REASON = "Khung giờ này tôi bận";
const QUICK_REASONS = [
  BUSY_REASON,
  "Căn đang sửa chữa",
  "Tôi đã có lịch xem khác giờ này",
];

type View = "pending" | "upcoming" | "past";
const VIEWS: { key: View; label: string; empty: string }[] = [
  {
    key: "pending",
    label: "Cần phản hồi",
    empty: "Bạn đã trả lời hết các yêu cầu. 👍",
  },
  {
    key: "upcoming",
    label: "Sắp tới",
    empty: "Chưa có buổi xem nào đã xác nhận.",
  },
  { key: "past", label: "Đã qua", empty: "Chưa có buổi xem nào đã qua." },
];

/** Who is asking: the buyer's name (their phone is never shown to the seller at this stage). */
function buyerName(b: Booking): string {
  return b.customer_name ?? b.buyer_ref.replace("Buyer", "Người mua");
}

/** "1 giờ 20" / "35 phút" */
function duration(ms: number): string {
  const minutes = Math.max(1, Math.round(ms / 60_000));
  if (minutes < 60) return `${minutes} phút`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} giờ ${m}` : `${h} giờ`;
}

/** "S1.08-2410" from "Vinhomes Ocean Park 1 · The Sapphire 1 - S1.08 · S1.08-2410" */
/** The time an answer would take: the new time asked for, or the viewing's own time. */
function askedWindow(b: Booking): [number, number] {
  return b.status === "RESCHEDULE_REQUESTED" && b.proposed_start_at && b.proposed_end_at
    ? [Date.parse(b.proposed_start_at), Date.parse(b.proposed_end_at)]
    : [Date.parse(b.start_at), Date.parse(b.end_at)];
}

/** Other unanswered requests (on any of the seller's homes) that confirming `b` would close. */
function overlapping(b: Booking, pending: Booking[]): Booking[] {
  const [start, end] = askedWindow(b);
  return pending.filter((o) => {
    if (o.id === b.id) return false;
    const [s, e] = askedWindow(o);
    return s < end && e > start;
  });
}

function unitOf(b: Booking): string {
  return b.property_label.split(" · ").at(-1) ?? b.property_label;
}

/** "The Sapphire 1 - S1.08 · Vinhomes Ocean Park 1" from the same label */
function placeOf(b: Booking): string {
  const [project, building] = b.property_label.split(" · ");
  return building ? `${building} · ${project}` : project;
}

/** Re-render every 30 s so countdowns stay right. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  return now;
}

/** A confirmed viewing whose time is over and whose outcome the owner has not recorded yet. */
function awaitingOutcome(b: Booking, now: number): boolean {
  return b.status === "CONFIRMED" && new Date(b.end_at).getTime() <= now;
}

function statusChip(b: Booking, now: number): { text: string; tone: string } {
  if (awaitingOutcome(b, now)) return { text: "Ghi nhận kết quả", tone: "bg-blush text-brand-900" };
  if (b.status === "REQUESTED" && needsAnswer(b, now))
    return { text: "Chờ bạn xác nhận", tone: "bg-blush text-brand-900" };
  if (b.status === "RESCHEDULE_REQUESTED" && needsAnswer(b, now))
    return { text: "Xin đổi lịch", tone: "bg-blush text-brand-900" };
  if (b.status === "CONFIRMED")
    return { text: "Đã xác nhận", tone: "bg-leaf text-leaf-ink" };
  if (WAITING.has(b.status))
    return { text: "Đã qua giờ xem", tone: "bg-sand text-muted" };
  return { text: BOOKING_STATUS[b.status], tone: "bg-sand text-muted" };
}

/**
 * Seller side of the viewing flow (design: list on the left, the request on the right): confirm (HITL, AC-05)
 * or reject; privacy level 1 — the seller never sees the buyer's name or phone (AC-03).
 */
export function OwnerBookingsPage() {
  const [params, setParams] = useSearchParams();
  const bookings = useOwnerBookings();
  const responseHours = useOwnerOverview().data?.response_hours;
  const now = useNow();

  const all = bookings.data ?? [];
  // Requests whose viewing time already passed can no longer be answered: they go to "Đã qua"
  const lists: Record<View, Booking[]> = {
    // To answer, and past viewings waiting for "Đã xem xong" / "Khách không đến"
    pending: all
      .filter((b) => needsAnswer(b, now) || awaitingOutcome(b, now))
      .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    upcoming: all
      .filter(
        (b) => b.status === "CONFIRMED" && new Date(b.end_at).getTime() > now,
      )
      .sort((a, b) => a.start_at.localeCompare(b.start_at)),
    past: [],
  };
  lists.past = all
    .filter((b) => !lists.pending.includes(b) && !lists.upcoming.includes(b))
    .sort((a, b) => b.start_at.localeCompare(a.start_at));

  // ?booking=ID (from a notification or a click): open the list that holds it; ?view= from elsewhere
  const target = Number(params.get("booking")) || null;
  const holding = target
    ? VIEWS.find((v) => lists[v.key].some((b) => b.id === target))?.key
    : undefined;
  const asked = params.get("view") as View | null;
  const view: View =
    holding ??
    asked ??
    (lists.pending.length > 0 || !bookings.data ? "pending" : "upcoming");
  const shown = lists[view];
  const selected = shown.find((b) => b.id === target) ?? shown[0];

  if (bookings.isPending) return <Spinner />;
  if (bookings.isError)
    return (
      <ErrorBox error={bookings.error} onRetry={() => bookings.refetch()} />
    );

  return (
    <div className="space-y-5">
      <Tiles
        bookings={all}
        pending={lists.pending.length}
        now={now}
        responseHours={responseHours}
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(20rem,24rem)_minmax(0,1fr)]">
        <aside className="flex flex-col rounded-[28px] bg-sand p-5 lg:h-[calc(100dvh-16rem)] lg:min-h-[28rem]">
          <h1 className="font-display text-3xl font-bold">Yêu cầu xem nhà</h1>
          <div
            className="mt-4 flex w-fit rounded-full bg-paper p-1"
            role="tablist"
            aria-label="Danh sách"
          >
            {VIEWS.map((v) => (
              <button
                key={v.key}
                type="button"
                role="tab"
                aria-selected={view === v.key}
                onClick={() => setParams({ view: v.key })}
                className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${
                  view === v.key
                    ? "bg-brand-600 text-canvas"
                    : "text-ink hover:bg-sand"
                }`}
              >
                {v.label} · {lists[v.key].length}
              </button>
            ))}
          </div>

          <ul className="-mx-2 mt-4 flex-1 space-y-1 overflow-y-auto">
            {shown.length === 0 && (
              <li className="px-3 py-8 text-center text-sm text-muted">
                {VIEWS.find((v) => v.key === view)!.empty}
              </li>
            )}
            {shown.map((b) => {
              const chip = statusChip(b, now);
              const active = b.id === selected?.id;
              return (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => setParams({ view, booking: String(b.id) })}
                    aria-current={active}
                    className={`w-full rounded-2xl px-4 py-3.5 text-left transition ${active ? "bg-paper shadow-sm" : "hover:bg-paper/50"}`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-display text-lg font-bold">
                        {buyerName(b)}
                      </span>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${chip.tone}`}
                      >
                        {chip.text}
                      </span>
                    </span>
                    <span className="mt-0.5 block text-sm text-muted">
                      Căn {unitOf(b)} · gửi {formatDateTime(b.created_at)}
                    </span>
                    <span className="mt-1 block font-semibold">
                      {formatTimeRange(
                        b.proposed_start_at ?? b.start_at,
                        b.proposed_end_at ?? b.end_at,
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="relative overflow-hidden rounded-[28px] bg-paper lg:h-[calc(100dvh-16rem)] lg:min-h-[28rem]">
          {selected ? (
            <RequestDetail
              key={selected.id}
              booking={selected}
              responseHours={responseHours}
              now={now}
              clashes={overlapping(selected, lists.pending)}
            />
          ) : (
            <div className="grid h-full min-h-72 place-items-center p-8 text-center text-muted">
              Khi người mua đặt lịch xem căn của bạn qua Trợ lý AI, yêu cầu sẽ
              hiện ở đây.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/** The seller's numbers at a glance (design: four small cards above the requests). */
function Tiles({
  bookings,
  pending,
  now,
  responseHours,
}: {
  bookings: Booking[];
  pending: number;
  now: number;
  responseHours?: number;
}) {
  const listings = useOwnerProperties();
  const weekEnd = now + 7 * 86_400_000;
  const upcoming = bookings.filter(
    (b) =>
      b.status === "CONFIRMED" &&
      new Date(b.end_at).getTime() > now &&
      new Date(b.start_at).getTime() <= weekEnd,
  ).length;
  // How fast the seller answers: from the request to their confirm / reject (not requests the system closed)
  const answered = bookings.filter((b) => b.responded_at && !b.closed_by_system);
  const avg = answered.length
    ? answered.reduce(
        (sum, b) =>
          sum +
          (new Date(b.responded_at!).getTime() -
            new Date(b.created_at).getTime()),
        0,
      ) / answered.length
    : null;
  const selling = listings.data?.filter((p) => p.status === "AVAILABLE").length;

  const tiles: {
    label: string;
    value: string;
    hint: string;
    urgent?: boolean;
  }[] = [
    {
      label: "Chờ bạn xác nhận",
      value: String(pending),
      hint: responseHours
        ? `Trả lời trong ${responseHours} giờ (buổi xem gần thì trước giờ xem 1 tiếng) để giữ điểm uy tín`
        : "Yêu cầu đang chờ bạn",
      urgent: pending > 0,
    },
    {
      label: "Lịch sắp tới",
      value: String(upcoming),
      hint: "Trong 7 ngày tới",
    },
    {
      label: "Thời gian phản hồi TB",
      value: avg === null ? "—" : duration(avg),
      hint: answered.length
        ? `Từ ${answered.length} lần bạn đã trả lời`
        : "Chưa có lần trả lời nào",
    },
    {
      label: "Căn đang đăng",
      value: selling === undefined ? "…" : String(selling),
      hint: "Đã xác thực pháp lý",
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((t) => (
        <div
          key={t.label}
          className={`rounded-[22px] px-5 py-4 ${t.urgent ? "bg-blush" : "bg-sand"}`}
        >
          <dt className="text-sm text-muted">{t.label}</dt>
          <dd
            className={`mt-1 font-display text-3xl font-bold leading-none ${t.urgent ? "text-brand-700" : ""}`}
          >
            {t.value}
          </dd>
          <dd className="mt-1.5 text-xs text-muted">{t.hint}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Time left before an unanswered request goes to the investor's staff (24 h, but at the latest 1 h before the viewing). */
function deadline(
  b: Booking,
  responseHours: number,
  now: number,
): { text: string; late: boolean; overdue?: boolean } {
  const due = b.respond_by
    ? new Date(b.respond_by).getTime()
    : new Date(b.created_at).getTime() + responseHours * 3_600_000;
  const left = due - now;
  if (left <= 0)
    return {
      text: "Đã quá hạn trả lời",
      late: true,
      overdue: true,
    };
  const minutes = Math.ceil(left / 60_000);
  return {
    text: `Còn ${minutes >= 60 ? `${Math.floor(minutes / 60)} giờ ${minutes % 60} phút` : `${minutes} phút`} để phản hồi`,
    late: minutes <= 60,
  };
}

/** One request: when, who (anonymous), and the seller's answer at the bottom. */
function RequestDetail({
  booking: b,
  responseHours,
  now,
  clashes,
}: {
  booking: Booking;
  responseHours?: number;
  now: number;
  /** Other requests at an overlapping time: confirming this one closes them */
  clashes: Booking[];
}) {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [reason, setReason] = useState("");
  // "Khung giờ này tôi bận": also close that time so other buyers are not offered it
  const [closeTime, setCloseTime] = useState(true);
  const path = { params: { path: { booking_id: b.id } } };
  const onSuccess = () => {
    setRejecting(false);
    setSuggesting(false);
    queryClient.invalidateQueries({ queryKey: ["owner-bookings"] });
    queryClient.invalidateQueries({ queryKey: ["owner-overview"] });
  };
  const approve = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/owner/bookings/{booking_id}/approve", path)),
    onSuccess,
  });
  const reject = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/owner/bookings/{booking_id}/reject", {
          ...path,
          body: { reason, close_time: reason === BUSY_REASON && closeTime },
        }),
      ),
    onSuccess,
  });
  const complete = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/owner/bookings/{booking_id}/complete", path)),
    onSuccess,
  });
  const noShow = useMutation({
    mutationFn: () => call(api.POST("/api/v1/owner/bookings/{booking_id}/no-show", path)),
    onSuccess,
  });
  const busy = approve.isPending || reject.isPending || complete.isPending || noShow.isPending;
  const error = approve.error ?? reject.error ?? complete.error ?? noShow.error;

  const answerable = needsAnswer(b, now);
  const rescheduling = b.status === "RESCHEDULE_REQUESTED";
  const canComplete =
    b.status === "CONFIRMED" && new Date(b.start_at).getTime() <= now;
  const chip = statusChip(b, now);
  const due =
    b.status === "REQUESTED" && answerable && responseHours
      ? deadline(b, responseHours, now)
      : null;
  const buyer = buyerName(b);
  const budget =
    b.buyer_budget_min_vnd || b.buyer_budget_max_vnd
      ? b.buyer_budget_min_vnd && b.buyer_budget_max_vnd
        ? `${formatVnd(b.buyer_budget_min_vnd)} – ${formatVnd(b.buyer_budget_max_vnd)}`
        : b.buyer_budget_max_vnd
          ? `Tới ${formatVnd(b.buyer_budget_max_vnd)}`
          : `Từ ${formatVnd(b.buyer_budget_min_vnd!)}`
      : "Chưa cho biết";

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-5 overflow-y-auto p-6 md:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-xs text-muted">
              {b.deal_code} · gửi {formatDateTime(b.created_at)}
            </p>
            <h2 className="mt-1 font-display text-3xl font-bold leading-tight">
              {buyer} muốn xem {unitOf(b)}
            </h2>
            <p className="text-muted">{placeOf(b)}</p>
          </div>
          <span
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${chip.tone}`}
          >
            {chip.text}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-3xl bg-sand/70 px-5 py-4">
          <svg
            viewBox="0 0 24 24"
            className="size-6 text-brand-700"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <rect x="3" y="5" width="18" height="16" rx="3" />
            <path d="M3 10h18M8 3v4M16 3v4" strokeLinecap="round" />
          </svg>
          <div className="flex-1">
            <p className="font-display text-xl font-bold">
              {formatTimeRange(b.start_at, b.end_at)}
            </p>
            {rescheduling && b.proposed_start_at && b.proposed_end_at && (
              <p className="text-sm font-semibold text-brand-700">
                Người mua xin đổi sang{" "}
                {formatTimeRange(b.proposed_start_at, b.proposed_end_at)}
              </p>
            )}
          </div>
          {due && (
            <span
              className={`rounded-full bg-paper px-3 py-1 text-xs font-semibold ${due.late ? "text-red-700" : "text-ink"}`}
            >
              {due.text}
            </span>
          )}
          {due?.overdue && (
            // The request is still the seller's to answer; the investor's staff were only told and may call
            <p className="basis-full text-sm text-ink/80">
              Đã quá hạn trả lời
              {b.respond_by ? ` (hạn: ${formatDateTime(b.respond_by)})` : ""}, nên nhân viên Chủ đầu tư đã được báo
              và có thể gọi nhắc bạn. Yêu cầu vẫn là của bạn: bạn vẫn xác nhận, từ chối hoặc đề xuất giờ khác được tới
              trước giờ xem.
            </p>
          )}
          {b.hold_status === "ACTIVE" && (
            <span className="rounded-full bg-leaf px-3 py-1 text-xs font-semibold text-leaf-ink">
              Căn được giữ cho buổi xem
            </span>
          )}
        </div>

        <div className="rounded-3xl bg-canvas/60 p-5">
          <p className="font-display text-lg font-bold">{buyer}</p>
          <dl className="mt-3 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted">Ngân sách</dt>
              <dd className="font-semibold">{budget}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Ghi chú của người mua</dt>
              <dd className="font-semibold">{b.customer_note || "Không có"}</dd>
            </div>
          </dl>
          <p className="mt-4 flex items-center gap-2 text-sm text-muted">
            <svg
              viewBox="0 0 24 24"
              className="size-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <rect x="5" y="11" width="14" height="10" rx="2" />
              <path d="M8 11V8a4 4 0 0 1 8 0v3" />
            </svg>
            Số điện thoại người mua luôn được ẩn; hai bên chỉ liên hệ trực tiếp khi cùng muốn tiếp tục giao dịch.
          </p>
        </div>

        {b.rejection_reason && !answerable && (
          <p className="text-sm text-muted">Lý do: {b.rejection_reason}</p>
        )}
        {WAITING.has(b.status) && !answerable && (
          <p className="text-sm text-muted">
            Giờ xem đã qua mà yêu cầu chưa được trả lời.
          </p>
        )}
        {error && <ErrorBox error={error} />}

        {rejecting && (
          <form
            className="space-y-2 rounded-3xl bg-sand/60 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              reject.mutate();
            }}
          >
            <p className="text-sm font-semibold">
              {rescheduling ? "Vì sao bạn giữ giờ cũ?" : "Vì sao bạn từ chối?"}{" "}
              (người mua sẽ thấy)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setReason(r)}
                  className={`rounded-full border px-3 py-1 text-xs font-semibold ${reason === r ? "border-brand-600 bg-brand-600 text-canvas" : "border-ink/15 bg-paper"}`}
                >
                  {r}
                </button>
              ))}
            </div>
            {reason === BUSY_REASON && !rescheduling && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={closeTime} onChange={(e) => setCloseTime(e.target.checked)} />
                Đóng luôn khung giờ này để người mua khác không xin vào giờ đó
              </label>
            )}
            <div className="flex flex-wrap gap-2">
              <label htmlFor={`reason-${b.id}`} className="sr-only">
                Lý do
              </label>
              <input
                id={`reason-${b.id}`}
                className="min-w-0 flex-1 rounded-full border border-ink/10 bg-paper px-4 py-2 outline-none focus:border-brand-500"
                required
                minLength={3}
                autoFocus
                placeholder="Hoặc tự nhập lý do"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <button
                type="submit"
                className="rounded-full bg-red-700 px-4 py-2 text-sm font-semibold text-white"
                disabled={busy}
              >
                Gửi
              </button>
              <button
                type="button"
                className="rounded-full px-4 py-2 text-sm font-semibold hover:bg-paper"
                onClick={() => setRejecting(false)}
              >
                Thôi
              </button>
            </div>
          </form>
        )}
      </div>

      {suggesting && (
        <SuggestTimes booking={b} onDone={onSuccess} onCancel={() => setSuggesting(false)} />
      )}

      {(answerable || canComplete) && !rejecting && !suggesting && (
        <div className="flex flex-wrap items-center gap-3 border-t border-line bg-sand/60 px-6 py-4 md:px-8">
          {answerable && (
            <>
              {clashes.length > 0 && (
                <p className="basis-full rounded-2xl bg-amber-50 px-4 py-2.5 text-sm text-amber-900 ring-1 ring-amber-200">
                  <strong>Bạn có {clashes.length} yêu cầu khác cùng giờ</strong> (
                  {clashes.map((c) => `${buyerName(c)} · ${unitOf(c)}`).join("; ")}). Bạn không thể tiếp hai khách
                  cùng lúc, kể cả ở hai căn khác nhau: xác nhận người này sẽ tự đóng{" "}
                  {clashes.length > 1 ? "các yêu cầu đó" : "yêu cầu đó"}, và Trợ lý AI sẽ mời người mua chọn giờ khác.
                </p>
              )}
              <button
                type="button"
                className="rounded-full bg-brand-600 px-6 py-3 font-display text-base font-bold text-canvas shadow-sm hover:bg-brand-700 disabled:opacity-50"
                disabled={busy}
                onClick={() => approve.mutate()}
              >
                {rescheduling ? "Đồng ý giờ mới" : "Xác nhận lịch"}
              </button>
              <button
                type="button"
                className={
                  rescheduling
                    ? "rounded-full px-5 py-3 font-display text-base font-bold text-brand-700 hover:bg-paper"
                    : "rounded-full bg-red-600 px-6 py-3 font-display text-base font-bold text-white shadow-sm hover:bg-red-700 disabled:opacity-50"
                }
                disabled={busy}
                onClick={() => setRejecting(true)}
              >
                {rescheduling ? "Giữ giờ cũ" : "Từ chối"}
              </button>
              {!rescheduling && (
                <button
                  type="button"
                  className="rounded-full border border-ink/15 bg-paper px-5 py-3 font-display text-base font-bold hover:bg-canvas"
                  disabled={busy}
                  onClick={() => setSuggesting(true)}
                >
                  Đề xuất giờ khác
                </button>
              )}
            </>
          )}
          {canComplete && (
            <>
              <p className="basis-full text-sm text-muted">Buổi xem đã tới giờ: khách có đến không?</p>
              <button
                type="button"
                className="rounded-full bg-brand-600 px-5 py-3 font-display text-base font-bold text-canvas hover:bg-brand-700"
                disabled={busy}
                onClick={() => complete.mutate()}
              >
                Đã xem xong
              </button>
              <button
                type="button"
                className="rounded-full border border-ink/15 bg-paper px-5 py-3 font-semibold hover:bg-canvas"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`Ghi nhận ${buyer} không đến buổi xem này? Người mua sẽ được báo và có thể phản hồi.`))
                    noShow.mutate();
                }}
              >
                Khách không đến
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * "Đề xuất giờ khác": the seller cannot take this time and offers up to three of their own free times instead.
 * The request closes; the buyer gets the times and books one in a tap.
 */
function SuggestTimes({ booking: b, onDone, onCancel }: { booking: Booking; onDone: () => void; onCancel: () => void }) {
  const [picked, setPicked] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const slots = useQuery({
    queryKey: ["owner-slots", b.property_id],
    queryFn: () =>
      call(api.GET("/api/v1/owner/properties/{property_id}/slots", { params: { path: { property_id: b.property_id } } })),
  });
  const send = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/owner/bookings/{booking_id}/reject", {
          params: { path: { booking_id: b.id } },
          body: { reason: note.trim() || "Giờ này tôi không tiếp được, mời bạn chọn giờ khác", suggested_starts: picked, close_time: false },
        }),
      ),
    onSuccess: onDone,
  });
  // Free times of this home, far enough ahead (2 h, as for any booking), other than the one asked for
  const earliest = Date.now() + 2 * 3_600_000;
  const options = (slots.data ?? [])
    .filter((s) => s.is_free && new Date(s.start_at).getTime() >= earliest && s.start_at !== b.start_at)
    .slice(0, 12);
  const toggle = (iso: string) =>
    setPicked((p) => (p.includes(iso) ? p.filter((x) => x !== iso) : p.length < 3 ? [...p, iso] : p));

  return (
    <div className="space-y-3 border-t border-line bg-sand/60 px-6 py-4 md:px-8">
      <p className="font-semibold">Chọn tối đa 3 giờ bạn tiếp được (người mua bấm một giờ là gửi lại yêu cầu)</p>
      {slots.isPending && <Spinner />}
      {send.error && <ErrorBox error={send.error} />}
      {slots.data && options.length === 0 && (
        <p className="text-sm text-muted">
          Bạn chưa mở giờ trống nào sắp tới cho căn này. Thêm khung giờ ở “Căn của tôi → Thay đổi khung giờ” rồi quay lại.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map((s) => (
          <button
            key={s.id}
            type="button"
            aria-pressed={picked.includes(s.start_at)}
            onClick={() => toggle(s.start_at)}
            className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${
              picked.includes(s.start_at) ? "border-brand-600 bg-brand-600 text-canvas" : "border-ink/15 bg-paper"
            }`}
          >
            {formatTimeRange(s.start_at, s.end_at)}
          </button>
        ))}
      </div>
      <input
        className="w-full rounded-full border border-ink/10 bg-paper px-4 py-2 outline-none focus:border-brand-500"
        placeholder="Lời nhắn cho người mua (không bắt buộc)"
        maxLength={300}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-full bg-brand-600 px-5 py-2.5 font-semibold text-canvas hover:bg-brand-700 disabled:opacity-50"
          disabled={picked.length === 0 || send.isPending}
          onClick={() => send.mutate()}
        >
          {send.isPending ? "Đang gửi..." : `Gửi ${picked.length || ""} giờ đề xuất`}
        </button>
        <button type="button" className="rounded-full px-4 py-2.5 font-semibold hover:bg-paper" onClick={onCancel}>
          Thôi
        </button>
      </div>
    </div>
  );
}
