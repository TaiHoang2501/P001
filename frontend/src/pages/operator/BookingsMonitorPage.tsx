import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Booking, BookingStatus } from "../../api/types";
import { BookingBadge, EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { BOOKING_STATUS, formatDateTime, formatTimeRange } from "../../lib/format";

const ACTIVE = new Set<BookingStatus>(["REQUESTED", "CONFIRMED", "RESCHEDULE_REQUESTED"]);

/**
 * Operator monitoring (spec §4.15 "Booking / viewing monitoring"). Sellers confirm viewings
 * themselves; the operator only watches and can cancel a stuck booking as a manual fallback.
 */
export function BookingsMonitorPage() {
  const [status, setStatus] = useState<BookingStatus | "">("");
  const bookings = useQuery({
    queryKey: ["operator-bookings", status],
    queryFn: () => call(api.GET("/api/v1/operator/bookings", { params: { query: { status: status || null } } })),
  });
  const all = useQuery({ queryKey: ["operator-bookings", ""], queryFn: () => call(api.GET("/api/v1/operator/bookings")) });
  const counts = all.data?.reduce<Record<string, number>>((acc, b) => ({ ...acc, [b.status]: (acc[b.status] ?? 0) + 1 }), {});

  return (
    <div>
      <PageHeader title="Giám sát lịch xem" subtitle="Chủ căn tự xác nhận lịch; Chủ đầu tư theo dõi và chỉ can thiệp khi có ngoại lệ." />
      <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto">
        {(["", ...Object.keys(BOOKING_STATUS)] as (BookingStatus | "")[]).map((s) => (
          <button
            key={s || "ALL"}
            role="tab"
            type="button"
            aria-selected={status === s}
            onClick={() => setStatus(s)}
            className={`shrink-0 rounded-lg px-3 py-2 text-sm font-medium ${status === s ? "bg-brand-600 text-white" : "bg-white text-muted hover:text-ink"}`}
          >
            {s ? BOOKING_STATUS[s] : "Tất cả"}
            {counts && <span className="ml-1.5 opacity-75">{s ? (counts[s] ?? 0) : all.data?.length}</span>}
          </button>
        ))}
      </div>
      {bookings.isPending && <Spinner />}
      {bookings.isError && <ErrorBox error={bookings.error} onRetry={() => bookings.refetch()} />}
      {bookings.data?.length === 0 && <EmptyState title="Không có lịch xem nào" />}
      <ul className="space-y-3">
        {bookings.data?.map((b) => (
          <BookingRow key={b.id} booking={b} />
        ))}
      </ul>
    </div>
  );
}

function BookingRow({ booking: b }: { booking: Booking }) {
  const queryClient = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/bookings/{booking_id}/cancel", { params: { path: { booking_id: b.id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["operator-bookings"] }),
  });

  return (
    <li className="card space-y-2 p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{b.property_label}</h3>
            <BookingBadge status={b.status} />
          </div>
          <p className="mt-1 text-sm">{formatTimeRange(b.start_at, b.end_at)}</p>
          <p className="mt-1 text-xs text-muted">
            Deal <span className="font-mono">{b.deal_code}</span> · {b.customer_name} ({b.customer_phone}) · qua{" "}
            {b.created_via === "AI_AGENT" ? "Trợ lý AI" : "Web"} · tạo {formatDateTime(b.created_at)}
            {b.hold_status && ` · Hold ${b.hold_status}`}
          </p>
          {b.rejection_reason && <p className="mt-1 text-sm text-red-700">Lý do từ chối: {b.rejection_reason}</p>}
        </div>
        {ACTIVE.has(b.status) && (
          <button
            type="button"
            className="btn-danger btn-sm"
            disabled={cancel.isPending}
            onClick={() => {
              if (window.confirm("Hủy lịch xem này thay cho các bên (xử lý ngoại lệ)?")) cancel.mutate();
            }}
          >
            Hủy (ngoại lệ)
          </button>
        )}
      </div>
      {cancel.isError && <ErrorBox error={cancel.error} />}
    </li>
  );
}
