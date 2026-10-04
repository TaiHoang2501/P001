import { useQuery } from "@tanstack/react-query";

import { api, call } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BookingBadge, ErrorBox, Spinner } from "../components/ui";
import { formatTimeRange } from "../lib/format";
import { BackButton } from "./shared";

/** "Lịch xem của tôi" inside the agent chat; each viewing opens its status card. */
export function BookingsListCard({
  onBack,
  onOpenStatus,
}: {
  onBack: () => void;
  onOpenStatus: (bookingId: number) => void;
}) {
  const { user } = useAuth();
  const signedIn = user?.role === "CUSTOMER";
  const bookings = useQuery({
    queryKey: ["my-bookings"],
    queryFn: () => call(api.GET("/api/v1/bookings")),
    enabled: signedIn,
  });

  return (
    <section className="card w-full max-w-xl space-y-3 p-4 shadow-sm sm:p-5" aria-label="Lịch xem của tôi">
      <BackButton onClick={onBack}>Quay lại</BackButton>
      <h3 className="text-lg font-bold">Lịch xem của tôi</h3>
      {!signedIn && <p className="text-sm text-muted">Bạn chưa có tài khoản: lịch xem sẽ hiện ở đây sau khi bạn gửi yêu cầu xem nhà.</p>}
      {bookings.isPending && signedIn && <Spinner />}
      {bookings.isError && <ErrorBox error={bookings.error} onRetry={() => bookings.refetch()} />}
      {bookings.data?.length === 0 && <p className="text-sm text-muted">Bạn chưa đặt lịch xem nào. Hãy kể cho Trợ lý AI căn bạn muốn tìm.</p>}
      <ul className="space-y-2">
        {bookings.data?.map((b) => (
          <li key={b.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-medium">{b.property_label}</span>
                <BookingBadge status={b.status} />
              </div>
              <p className="text-xs text-muted">
                {formatTimeRange(b.start_at, b.end_at)} · <span className="font-mono">{b.deal_code}</span>
              </p>
            </div>
            <button
              type="button"
              className="btn btn-sm border border-brand-600 text-brand-600 hover:bg-brand-50"
              onClick={() => onOpenStatus(b.id)}
            >
              Theo dõi
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
