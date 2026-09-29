import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Booking, BookingStatus } from "../../api/types";
import { BookingBadge, EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { BOOKING_STATUS, formatTimeRange, formatVnd } from "../../lib/format";

const FILTERS: (BookingStatus | "ALL")[] = ["REQUESTED", "RESCHEDULE_REQUESTED", "CONFIRMED", "COMPLETED", "ALL"];

/** Seller side of the viewing flow: confirm (HITL, AC-05) or reject; privacy level 1 — no buyer contact (AC-03). */
export function OwnerBookingsPage() {
  const [filter, setFilter] = useState<BookingStatus | "ALL">("REQUESTED");
  const bookings = useQuery({
    queryKey: ["owner-bookings", filter],
    queryFn: () =>
      call(api.GET("/api/v1/owner/bookings", { params: { query: filter === "ALL" ? {} : { status: filter } } })),
  });

  return (
    <div>
      <PageHeader
        title="Yêu cầu xem nhà"
        subtitle="Lịch chỉ có hiệu lực khi bạn xác nhận; khi đó căn được giữ riêng cho buổi xem trong đúng khung giờ."
      />
      <div className="mb-4 flex flex-wrap gap-1.5" role="tablist">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            role="tab"
            aria-selected={filter === f}
            onClick={() => setFilter(f)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${filter === f ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-white text-muted hover:text-ink"}`}
          >
            {f === "ALL" ? "Tất cả" : BOOKING_STATUS[f]}
          </button>
        ))}
      </div>
      {bookings.isPending && <Spinner />}
      {bookings.isError && <ErrorBox error={bookings.error} onRetry={() => bookings.refetch()} />}
      {bookings.data?.length === 0 && <EmptyState title="Không có yêu cầu nào" />}
      <ul className="space-y-3">
        {bookings.data?.map((b) => (
          <OwnerBookingRow key={b.id} booking={b} />
        ))}
      </ul>
    </div>
  );
}

function OwnerBookingRow({ booking: b }: { booking: Booking }) {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const path = { params: { path: { booking_id: b.id } } };
  const onSuccess = () => {
    setRejecting(false);
    queryClient.invalidateQueries({ queryKey: ["owner-bookings"] });
  };

  const approve = useMutation({ mutationFn: () => call(api.POST("/api/v1/owner/bookings/{booking_id}/approve", path)), onSuccess });
  const reject = useMutation({
    mutationFn: () => call(api.POST("/api/v1/owner/bookings/{booking_id}/reject", { ...path, body: { reason } })),
    onSuccess,
  });
  const complete = useMutation({ mutationFn: () => call(api.POST("/api/v1/owner/bookings/{booking_id}/complete", path)), onSuccess });
  const busy = approve.isPending || reject.isPending || complete.isPending;
  const error = approve.error ?? reject.error ?? complete.error;
  const deciding = b.status === "REQUESTED" || b.status === "RESCHEDULE_REQUESTED";
  const budget =
    b.buyer_budget_min_vnd || b.buyer_budget_max_vnd
      ? `${b.buyer_budget_min_vnd ? formatVnd(b.buyer_budget_min_vnd) : "?"} – ${b.buyer_budget_max_vnd ? formatVnd(b.buyer_budget_max_vnd) : "?"}`
      : null;

  return (
    <li className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{b.property_label}</h3>
            <BookingBadge status={b.status} />
          </div>
          <p className="mt-1 text-sm">{formatTimeRange(b.start_at, b.end_at)}</p>
          {b.status === "RESCHEDULE_REQUESTED" && b.proposed_start_at && b.proposed_end_at && (
            <p className="mt-1 text-sm text-violet-800">Người mua đề nghị đổi sang {formatTimeRange(b.proposed_start_at, b.proposed_end_at)}</p>
          )}
          <p className="mt-1 text-xs text-muted">
            {b.buyer_ref}
            {budget && ` · Ngân sách ${budget}`} · Deal <span className="font-mono">{b.deal_code}</span>
            {b.hold_status === "ACTIVE" && " · Căn đang được giữ cho buổi xem"}
          </p>
          {b.customer_note && <p className="mt-1 text-sm text-muted">Ghi chú: {b.customer_note}</p>}
        </div>
        {!rejecting && (
          <div className="flex flex-wrap gap-2">
            {deciding && (
              <>
                <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={() => approve.mutate()}>
                  {b.status === "RESCHEDULE_REQUESTED" ? "Đồng ý giờ mới" : "Xác nhận lịch"}
                </button>
                <button type="button" className="btn-danger btn-sm" disabled={busy} onClick={() => setRejecting(true)}>
                  {b.status === "RESCHEDULE_REQUESTED" ? "Giữ giờ cũ" : "Từ chối"}
                </button>
              </>
            )}
            {b.status === "CONFIRMED" && new Date(b.start_at) <= new Date() && (
              <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={() => complete.mutate()}>
                Đã xem xong
              </button>
            )}
          </div>
        )}
      </div>
      {rejecting && (
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            reject.mutate();
          }}
        >
          <label htmlFor={`reason-${b.id}`} className="sr-only">
            Lý do
          </label>
          <input
            id={`reason-${b.id}`}
            className="input min-w-0 flex-1"
            required
            minLength={3}
            autoFocus
            placeholder="Lý do (người mua sẽ thấy), VD: Khung giờ này tôi bận"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button type="submit" className="btn-danger btn-sm" disabled={busy}>
            Gửi
          </button>
          <button type="button" className="btn-secondary btn-sm" onClick={() => setRejecting(false)}>
            Thôi
          </button>
        </form>
      )}
      {error && <ErrorBox error={error} />}
    </li>
  );
}
