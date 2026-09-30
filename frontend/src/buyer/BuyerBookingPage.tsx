import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router";

import { api, call } from "../api/client";
import type { Booking, Deal } from "../api/types";
import { BookingBadge, ErrorBox, Notice, Spinner } from "../components/ui";
import { formatDateTime, formatTimeRange } from "../lib/format";
import { CheckCircleIcon, CheckIcon, CopyIcon } from "./icons";
import { BackLink } from "./shared";

const STEPS = ["Gửi yêu cầu", "Chờ chủ căn xác nhận", "Xác nhận lịch", "Xem nhà", "Quan tâm", "Gửi yêu cầu mua", "Hoàn tất"];

/** How far the deal got along STEPS (index of the step in progress; STEPS.length when done). */
function progressOf(booking: Booking, deal?: Deal): number {
  switch (deal?.status) {
    case "COMPLETED":
      return STEPS.length;
    case "NEGOTIATING":
    case "TRANSACTION_SUPPORT":
      return 6;
    case "INTERESTED":
      return 5;
    case "VIEWED":
      return 4;
    default:
      break;
  }
  if (booking.status === "COMPLETED") return 4;
  if (booking.status === "CONFIRMED") return 3;
  return 1;
}

const ENDED = new Set<Booking["status"]>(["REJECTED", "CANCELLED", "NO_SHOW"]);

/** Wireframe 1.6: request sent + deal tracking. */
export function BuyerBookingPage() {
  const id = Number(useParams().id);
  const justCreated = (useLocation().state as { justCreated?: boolean } | null)?.justCreated ?? false;
  const [copied, setCopied] = useState(false);

  const booking = useQuery({
    queryKey: ["my-bookings", id],
    queryFn: () => call(api.GET("/api/v1/bookings/{booking_id}", { params: { path: { booking_id: id } } })),
    refetchInterval: 30_000,
  });
  const dealId = booking.data?.deal_id;
  const deal = useQuery({
    queryKey: ["deal", dealId],
    queryFn: () => call(api.GET("/api/v1/deals/{deal_id}", { params: { path: { deal_id: dealId! } } })),
    enabled: dealId !== undefined,
    refetchInterval: 30_000,
  });

  if (booking.isPending) return <Spinner />;
  if (booking.isError) return <ErrorBox error={booking.error} onRetry={() => booking.refetch()} />;
  const b = booking.data;
  const ended = ENDED.has(b.status) || deal.data?.status === "CLOSED";
  const progress = progressOf(b, deal.data);

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(b.deal_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: the code stays visible to copy by hand
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-4">
      {!justCreated && <BackLink to="/buyer/bookings">Lịch xem của tôi</BackLink>}

      <section className="card space-y-6 p-6 shadow-sm">
        <div className="text-center">
          {justCreated && (
            <>
              <span className="mx-auto grid size-14 place-items-center rounded-full text-emerald-500">
                <CheckCircleIcon className="size-14" strokeWidth={1.4} />
              </span>
              <h1 className="mt-2 text-xl font-bold">Đã gửi yêu cầu xem nhà!</h1>
              <p className="mt-1 text-sm text-muted">Chủ căn sẽ phản hồi trong thời gian sớm nhất. Bạn có thể theo dõi trạng thái tại đây.</p>
            </>
          )}
          {!justCreated && <h1 className="text-xl font-bold">Theo dõi lịch xem</h1>}
        </div>

        <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-slate-50 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs text-muted">Deal ID</p>
            <p className="font-mono font-semibold">{b.deal_code}</p>
          </div>
          <button
            type="button"
            onClick={copyCode}
            className="grid size-9 place-items-center rounded-lg text-brand-600 hover:bg-brand-50"
            aria-label="Sao chép Deal ID"
            title={copied ? "Đã sao chép" : "Sao chép"}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
          </button>
        </div>

        <dl className="space-y-1 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <dt className="sr-only">Căn</dt>
            <dd className="font-medium">
              <Link to={`/buyer/properties/${b.property_id}`} className="hover:underline">
                {b.property_label}
              </Link>
            </dd>
            <BookingBadge status={b.status} />
          </div>
          <dt className="sr-only">Thời gian</dt>
          <dd className="text-muted">{formatTimeRange(b.start_at, b.end_at)}</dd>
          {b.proposed_start_at && b.proposed_end_at && (
            <dd className="text-violet-800">Đề nghị đổi sang {formatTimeRange(b.proposed_start_at, b.proposed_end_at)}</dd>
          )}
        </dl>

        {ended ? (
          <Notice tone="warning">
            Lịch xem này đã kết thúc ({b.status === "REJECTED" ? "chủ căn từ chối" : b.status === "NO_SHOW" ? "vắng mặt" : "đã hủy/đóng"}).
            {b.rejection_reason && <> Lý do: {b.rejection_reason}.</>} Hãy nhờ AI Agent tìm căn hoặc giờ khác.
          </Notice>
        ) : (
          <div>
            <h2 className="mb-3 font-semibold">Trạng thái</h2>
            <ol className="space-y-0">
              {STEPS.map((step, i) => {
                const done = i < progress;
                const current = i === progress;
                return (
                  <li key={step} className="relative flex items-start gap-3 pb-4 last:pb-0">
                    {i < STEPS.length - 1 && (
                      <span className={`absolute left-[9px] top-5 h-full w-0.5 ${done ? "bg-brand-600" : "bg-line"}`} aria-hidden="true" />
                    )}
                    <span
                      className={`relative grid size-5 shrink-0 place-items-center rounded-full ${
                        done ? "bg-brand-600 text-white" : current ? "border-2 border-brand-600 bg-white" : "border-2 border-line bg-white"
                      }`}
                    >
                      {done && <CheckIcon className="size-3" strokeWidth={3} />}
                    </span>
                    <span className={`flex-1 text-sm ${done || current ? "font-medium text-ink" : "text-muted"}`}>
                      {step}
                      {current && <span className="sr-only"> (đang chờ)</span>}
                    </span>
                    {i === 0 && <span className="text-xs text-muted">{formatDateTime(b.created_at)}</span>}
                  </li>
                );
              })}
            </ol>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Link to="/buyer/bookings" className="btn border border-brand-600 bg-white text-brand-600 hover:bg-brand-50">
            Xem chi tiết
          </Link>
          <Link to="/buyer" className="btn-secondary">
            Về trang chủ
          </Link>
        </div>
      </section>
    </div>
  );
}
