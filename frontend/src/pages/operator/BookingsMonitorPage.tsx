import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import type { Booking, BookingStatus } from "../../api/types";
import { BookingBadge, EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime, formatTimeRange } from "../../lib/format";
import { useJumpFlash } from "../../lib/jump";

const ACTIVE = new Set<BookingStatus>(["REQUESTED", "CONFIRMED", "RESCHEDULE_REQUESTED"]);

const started = (b: Booking) => Date.parse(b.start_at) <= Date.now();

/** Three groups instead of a tab per status: what may need the operator, what is ahead, what is over. */
type Group = "attention" | "upcoming" | "ended" | "all";
const GROUPS: { key: Group; label: string; hint: string; test: (b: Booking) => boolean }[] = [
  {
    key: "attention",
    label: "Cần chú ý",
    hint: "Yêu cầu chủ căn chưa trả lời, xin đổi lịch, và buổi xem đã qua giờ mà chưa ghi nhận kết quả",
    test: (b) => b.status === "REQUESTED" || b.status === "RESCHEDULE_REQUESTED" || (b.status === "CONFIRMED" && started(b)),
  },
  {
    key: "upcoming",
    label: "Sắp tới",
    hint: "Lịch đã xác nhận, chưa tới giờ xem",
    test: (b) => b.status === "CONFIRMED" && !started(b),
  },
  {
    key: "ended",
    label: "Đã kết thúc",
    hint: "Đã xem, không đến, bị từ chối, đã hủy, hết hạn…",
    test: (b) => !ACTIVE.has(b.status),
  },
  { key: "all", label: "Tất cả", hint: "Mọi lịch xem", test: () => true },
];

/**
 * Operator monitoring (spec §4.15 "Booking / viewing monitoring"). Sellers confirm viewings
 * themselves; the operator only watches and can cancel a stuck booking as a manual fallback.
 */
export function BookingsMonitorPage() {
  const [params] = useSearchParams();
  // Opened from a notification (?booking=ID): show every viewing so that one is in the list, and light it up
  const opened = Number(params.get("booking")) || null;
  const [group, setGroup] = useState<Group>("attention");
  useEffect(() => {
    if (opened) setGroup("all");
  }, [opened, params]);
  const bookings = useQuery({ queryKey: ["operator-bookings"], queryFn: () => call(api.GET("/api/v1/operator/bookings")) });
  const shown = bookings.data?.filter(GROUPS.find((g) => g.key === group)!.test) ?? [];
  // Several requests for one home at one time: a hot spot the operator may want to watch
  const slot = (b: Booking) => `${b.property_id}@${b.start_at}`;
  const sameTime = new Map<string, number>();
  for (const b of bookings.data ?? []) if (b.status === "REQUESTED") sameTime.set(slot(b), (sameTime.get(slot(b)) ?? 0) + 1);

  return (
    <div>
      <PageHeader title="Giám sát lịch xem" subtitle="Chủ căn tự xác nhận lịch; Chủ đầu tư theo dõi và chỉ can thiệp khi có ngoại lệ." />
      <div role="tablist" className="mb-4 flex flex-wrap gap-1">
        {GROUPS.map((g) => (
          <button
            key={g.key}
            role="tab"
            type="button"
            title={g.hint}
            aria-selected={group === g.key}
            onClick={() => setGroup(g.key)}
            className={`rounded-lg px-3 py-2 text-sm font-medium ${group === g.key ? "bg-brand-600 text-white" : "bg-white text-muted hover:text-ink"}`}
          >
            {g.label}
            {bookings.data && <span className="ml-1.5 opacity-75">{bookings.data.filter(g.test).length}</span>}
          </button>
        ))}
      </div>
      {bookings.isPending && <Spinner />}
      {bookings.isError && <ErrorBox error={bookings.error} onRetry={() => bookings.refetch()} />}
      {bookings.data && shown.length === 0 && <EmptyState title="Không có lịch xem nào" />}
      <ul className="space-y-3">
        {shown.map((b) => (
          <BookingRow
            key={b.id}
            booking={b}
            opened={b.id === opened}
            sameTime={b.status === "REQUESTED" ? (sameTime.get(slot(b)) ?? 1) : 1}
          />
        ))}
      </ul>
    </div>
  );
}

function BookingRow({ booking: b, opened = false, sameTime }: { booking: Booking; opened?: boolean; sameTime: number }) {
  const flash = useJumpFlash(opened);
  const queryClient = useQueryClient();
  const cancel = useMutation({
    mutationFn: (reason: string) =>
      call(api.POST("/api/v1/operator/bookings/{booking_id}/cancel", { params: { path: { booking_id: b.id } }, body: { reason } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["operator-bookings"] }),
  });
  // Only before the viewing: afterwards what happened is recorded by the owner, not cancelled
  const cancellable = ACTIVE.has(b.status) && !started(b);

  return (
    <li ref={flash} className="card space-y-2 p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{b.property_label}</h3>
            <BookingBadge status={b.status} startAt={b.start_at} />
            {sameTime > 1 && (
              <span className="rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-medium text-orange-900">
                {sameTime} yêu cầu cùng giờ
              </span>
            )}
          </div>
          <p className="mt-1 text-sm">
            {formatTimeRange(b.start_at, b.end_at)}
            {b.status === "CONFIRMED" && b.hold_status === "ACTIVE" && (
              <span className="text-muted" title="Căn được khóa riêng cho buổi xem này, không ai đặt chồng giờ được">
                {" "}
                · đang giữ căn cho buổi xem
              </span>
            )}
          </p>
          <p className="mt-1 text-xs text-muted">
            Lịch #{b.id} · Deal <span className="font-mono">{b.deal_code}</span> · qua{" "}
            {b.created_via === "AI_AGENT" ? "Trợ lý AI" : "Web"} · tạo {formatDateTime(b.created_at)}
          </p>
          <p className="mt-1 text-xs text-muted">
            Người mua <Person name={b.customer_name} phone={b.customer_phone} /> · Chủ căn{" "}
            <Person name={b.owner_name} phone={b.owner_phone} />
          </p>
          {b.rejection_reason && <p className="mt-1 text-sm text-red-700">Lý do từ chối: {b.rejection_reason}</p>}
        </div>
        {cancellable && (
          <button
            type="button"
            className="rounded-lg px-2 py-1 text-xs font-medium text-muted underline-offset-2 hover:text-red-700 hover:underline"
            disabled={cancel.isPending}
            title="Chỉ dùng khi xử lý sự cố: hủy lịch thay cho các bên, cả hai được báo"
            onClick={() => {
              // Both sides read the reason, so it is asked for (at least 10 characters)
              const reason = window.prompt(
                `Hủy lịch #${b.id} (${b.customer_name ?? "người mua"}) thay cho các bên. Lý do (cả hai bên đều đọc, ít nhất 10 ký tự):`,
              );
              if (reason === null) return;
              if (reason.trim().length < 10) {
                window.alert("Lý do cần ít nhất 10 ký tự.");
                return;
              }
              cancel.mutate(reason.trim());
            }}
          >
            Hủy lịch…
          </button>
        )}
      </div>
      {cancel.isError && <ErrorBox error={cancel.error} />}
    </li>
  );
}

/** A name with a phone number that can be called in one tap. */
function Person({ name, phone }: { name?: string | null; phone?: string | null }) {
  return (
    <span className="text-ink">
      {name ?? "—"}
      {phone && (
        <>
          {" "}
          (
          <a href={`tel:${phone}`} className="underline-offset-2 hover:underline">
            {phone}
          </a>
          )
        </>
      )}
    </span>
  );
}
