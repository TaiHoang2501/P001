import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../api/client";
import type { Booking } from "../api/types";
import { BookingBadge, ErrorBox, Notice, Spinner } from "../components/ui";
import { formatDateTime, formatTimeRange } from "../lib/format";
import {
  CANCELLABLE,
  ENDED,
  endedLabel,
  StatusTimeline,
} from "./bookingStatus";
import { CheckIcon, CopyIcon } from "./icons";
import { BackButton } from "./shared";
import { AfterViewing } from "./AfterViewing";
import { ViewingPass } from "./ViewingPass";

export function useBooking(bookingId: number) {
  return useQuery({
    queryKey: ["my-bookings", bookingId],
    queryFn: () =>
      call(
        api.GET("/api/v1/bookings/{booking_id}", {
          params: { path: { booking_id: bookingId } },
        }),
      ),
    // The seller's answer shows up here without reloading
    refetchInterval: 30_000,
  });
}

/** Wireframe 1.6 inside the agent chat: deal + live status, with reschedule / cancel / see the home again. */
export function BookingStatusCard({
  bookingId,
  onBack,
  onReschedule,
  onViewProperty,
  onChanged,
}: {
  bookingId: number;
  onBack: () => void;
  onReschedule: (b: Booking) => void;
  onViewProperty: (propertyId: number) => void;
  /** After the buyer's own change, so the chat does not announce it as news */
  onChanged: (b: Booking) => void;
}) {
  const queryClient = useQueryClient();
  const booking = useBooking(bookingId);
  const dealId = booking.data?.deal_id;
  const deal = useQuery({
    queryKey: ["deal", dealId],
    queryFn: () =>
      call(
        api.GET("/api/v1/deals/{deal_id}", {
          params: { path: { deal_id: dealId! } },
        }),
      ),
    enabled: dealId !== undefined,
    refetchInterval: 30_000,
  });
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [copied, setCopied] = useState(false);

  const cancel = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/bookings/{booking_id}/cancel", {
          params: { path: { booking_id: bookingId } },
        }),
      ),
    onSuccess: (b) => {
      onChanged(b);
      setConfirmCancel(false);
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
    },
  });

  if (booking.isPending) return <Spinner label="Đang tải trạng thái..." />;
  if (booking.isError)
    return <ErrorBox error={booking.error} onRetry={() => booking.refetch()} />;
  const b = booking.data;
  const ended = ENDED.has(b.status) || deal.data?.status === "CLOSED";
  const upcoming = new Date(b.start_at) > new Date();

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(b.deal_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: the code stays visible
    }
  }

  return (
    <section
      className="card w-full max-w-xl space-y-4 p-4 shadow-sm sm:p-5"
      aria-label={`Trạng thái deal ${b.deal_code}`}
    >
      <BackButton onClick={onBack}>Quay lại</BackButton>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono font-semibold">{b.deal_code}</span>
            <BookingBadge status={b.status} />
          </div>
          <p className="mt-1 text-sm">{b.property_label}</p>
          <p className="text-sm text-muted">
            {formatTimeRange(b.start_at, b.end_at)}
          </p>
          {b.proposed_start_at && b.proposed_end_at && (
            <p className="text-sm text-violet-800">
              Đề nghị đổi sang{" "}
              {formatTimeRange(b.proposed_start_at, b.proposed_end_at)} — chờ
              chủ căn đồng ý. Lịch cũ vẫn giữ (mã QR bên dưới vẫn dùng được) cho tới khi chủ căn đồng ý giờ mới.
            </p>
          )}
          {b.hold_status === "ACTIVE" && (
            <p className="text-xs text-emerald-800">
              Căn được giữ riêng cho bạn trong khung giờ này.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={copyCode}
          className="grid size-9 shrink-0 place-items-center rounded-lg text-brand-600 hover:bg-brand-50"
          aria-label="Sao chép Deal ID"
          title={copied ? "Đã sao chép" : "Sao chép"}
        >
          {copied ? <CheckIcon /> : <CopyIcon />}
        </button>
      </div>

      {ended ? (
        <Notice tone="warning">
          Lịch xem này đã kết thúc ({endedLabel(b)}).
          {b.rejection_reason && <> Lý do: {b.rejection_reason}.</>} Nhắn Trợ lý
          AI để tìm giờ hoặc căn khác.
        </Notice>
      ) : (
        <StatusTimeline booking={b} deal={deal.data} compact />
      )}

      {/* The owner could not take this time and offered others: one tap sends a new request */}
      {b.status === "REJECTED" && (b.suggested_starts?.length ?? 0) > 0 && (
        <SuggestedTimes booking={b} onBooked={onChanged} />
      )}

      {/* Once the viewing time is over: how it went, or a disagreement with what was recorded */}
      <AfterViewing booking={b} onChanged={onChanged} />

      {/* Confirmed and not over yet: the QR to show at the building's gate */}
      {(b.status === "CONFIRMED" || b.status === "RESCHEDULE_REQUESTED") &&
        new Date(b.end_at).getTime() + 30 * 60_000 > Date.now() && <ViewingPass booking={b} />}

      {cancel.isError && <ErrorBox error={cancel.error} />}
      {confirmCancel ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm">
          <span className="flex-1">Hủy lịch xem này?</span>
          <button
            type="button"
            className="btn-danger btn-sm"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate()}
          >
            {cancel.isPending ? "Đang hủy..." : "Hủy lịch"}
          </button>
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => setConfirmCancel(false)}
          >
            Không
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {(b.status === "REQUESTED" || b.status === "CONFIRMED") &&
            upcoming && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => onReschedule(b)}
              >
                Đổi giờ
              </button>
            )}
          {CANCELLABLE.has(b.status) && upcoming && (
            <button
              type="button"
              className="btn-danger btn-sm"
              onClick={() => setConfirmCancel(true)}
            >
              Hủy lịch
            </button>
          )}
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => onViewProperty(b.property_id)}
          >
            Xem lại căn
          </button>
        </div>
      )}
    </section>
  );
}

/** "Chủ căn đề xuất giờ khác": the times the owner offered, each one a new viewing request in one tap. */
function SuggestedTimes({ booking: b, onBooked }: { booking: Booking; onBooked: (b: Booking) => void }) {
  const queryClient = useQueryClient();
  const upcoming = (b.suggested_starts ?? []).filter((t) => new Date(t).getTime() > Date.now());
  const book = useMutation({
    mutationFn: (start: string) =>
      call(api.POST("/api/v1/bookings", { body: { property_id: b.property_id, start_at: start } })),
    onSuccess: (next) => {
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
      queryClient.invalidateQueries({ queryKey: ["my-activity"] });
      onBooked(next);
    },
  });
  return (
    <div className="space-y-2 rounded-xl border border-brand-200 bg-brand-50 p-3">
      <p className="font-semibold">Chủ căn đề xuất giờ khác</p>
      {upcoming.length === 0 ? (
        <p className="text-sm text-muted">Các giờ chủ căn đề xuất đã qua. Nhắn Trợ lý AI để tìm giờ khác.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {upcoming.map((t) => (
              <button
                key={t}
                type="button"
                className="btn-secondary btn-sm"
                disabled={book.isPending}
                onClick={() => book.mutate(t)}
              >
                Đặt {formatDateTime(t)}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted">Bấm một giờ là yêu cầu được gửi lại cho chủ căn xác nhận.</p>
        </>
      )}
      {book.error && <ErrorBox error={book.error} />}
    </div>
  );
}
