import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, call } from "../api/client";
import type { Booking } from "../api/types";
import { BookingBadge, EmptyState, ErrorBox, Notice, PageHeader, Spinner } from "../components/ui";
import { ViewingTimePicker } from "../components/ViewingTimePicker";
import { formatTimeRange } from "../lib/format";

const CANCELLABLE = new Set<Booking["status"]>(["REQUESTED", "CONFIRMED", "RESCHEDULE_REQUESTED"]);

export function BuyerBookingsPage() {
  const queryClient = useQueryClient();
  const bookings = useQuery({ queryKey: ["my-bookings"], queryFn: () => call(api.GET("/api/v1/bookings")) });
  const [rescheduling, setRescheduling] = useState<number | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["my-bookings"] });

  const cancel = useMutation({
    mutationFn: (id: number) => call(api.POST("/api/v1/bookings/{booking_id}/cancel", { params: { path: { booking_id: id } } })),
    onSuccess: refresh,
  });
  const reschedule = useMutation({
    mutationFn: ({ id, startAt }: { id: number; startAt: string }) =>
      call(
        api.POST("/api/v1/bookings/{booking_id}/reschedule", {
          params: { path: { booking_id: id } },
          body: { start_at: startAt },
        }),
      ),
    onSuccess: () => {
      setRescheduling(null);
      refresh();
    },
  });

  return (
    <div>
      <PageHeader
        title="Lịch xem của tôi"
        subtitle="Yêu cầu được gửi thẳng tới chủ căn; lịch chỉ có hiệu lực khi chủ căn xác nhận."
      />
      {(cancel.isError || reschedule.isError) && (
        <div className="mb-4">
          <ErrorBox error={cancel.error ?? reschedule.error} />
        </div>
      )}
      {bookings.isPending && <Spinner />}
      {bookings.isError && <ErrorBox error={bookings.error} onRetry={() => bookings.refetch()} />}
      {bookings.data?.length === 0 && (
        <EmptyState title="Bạn chưa có lịch xem nào">
          <Link to="/buyer/chat" className="font-medium text-brand-700 hover:underline">
            Trò chuyện với AI Agent để tìm căn
          </Link>
        </EmptyState>
      )}
      <ul className="space-y-3">
        {bookings.data?.map((b) => {
          const upcoming = new Date(b.start_at) > new Date();
          return (
            <li key={b.id} className="card space-y-3 p-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/buyer/properties/${b.property_id}`} className="font-medium hover:underline">
                      {b.property_label}
                    </Link>
                    <BookingBadge status={b.status} />
                  </div>
                  <p className="mt-1 text-sm text-muted">
                    {formatTimeRange(b.start_at, b.end_at)} · Deal{" "}
                    <Link to={`/buyer/bookings/${b.id}`} className="font-mono text-brand-700 hover:underline">
                      {b.deal_code}
                    </Link>
                  </p>
                  {b.hold_status === "ACTIVE" && (
                    <p className="mt-1 text-xs text-emerald-800">Căn được giữ riêng cho bạn trong khung giờ này.</p>
                  )}
                  {b.proposed_start_at && b.proposed_end_at && (
                    <p className="mt-1 text-sm text-violet-800">
                      Đã đề nghị đổi sang {formatTimeRange(b.proposed_start_at, b.proposed_end_at)} — chờ chủ căn xác nhận.
                    </p>
                  )}
                  {b.rejection_reason && <p className="mt-1 text-sm text-red-700">Lý do từ chối: {b.rejection_reason}</p>}
                </div>
                <div className="flex gap-2">
                  {b.status === "CONFIRMED" && upcoming && (
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => setRescheduling(rescheduling === b.id ? null : b.id)}
                    >
                      Đổi lịch
                    </button>
                  )}
                  {CANCELLABLE.has(b.status) && upcoming && (
                    <button
                      type="button"
                      className="btn-danger btn-sm"
                      disabled={cancel.isPending}
                      onClick={() => {
                        if (window.confirm("Hủy lịch xem này?")) cancel.mutate(b.id);
                      }}
                    >
                      Hủy lịch
                    </button>
                  )}
                </div>
              </div>
              {rescheduling === b.id && (
                <div className="border-t border-line pt-3">
                  <Notice>Buổi xem giữ nguyên giờ cũ cho tới khi chủ căn đồng ý giờ mới.</Notice>
                  <div className="mt-3 max-w-sm">
                    <ViewingTimePicker
                      propertyId={b.property_id}
                      busy={reschedule.isPending}
                      submitLabel="Gửi đề nghị đổi lịch"
                      onPick={(startAt) => reschedule.mutate({ id: b.id, startAt })}
                    />
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
