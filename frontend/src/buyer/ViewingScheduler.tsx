import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError, call } from "../api/client";
import type { Booking, TimeWindow } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, Notice, Spinner } from "../components/ui";
import {
  formatTimeRange,
  formatVnd,
  timeOf,
  vnIso,
  vnToday,
} from "../lib/format";
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon } from "./icons";
import { GuestSignup } from "./GuestSignup";
import { useProperty } from "./PropertyDetailCard";
import { BackButton } from "./shared";

const DAYS_AHEAD = 14;
const DAYS_PER_PAGE = 3;
// The buyer picks a day; the agent's matching treats the whole daytime as their free window
const DAY_FROM = "08:00";
const DAY_TO = "20:00";

/** "2026-10-03" -> "Thứ 7" / "Chủ nhật" (the date string is already a Vietnam calendar day) */
function weekday(day: string): string {
  const n = new Date(`${day}T00:00:00Z`).getUTCDay();
  return n === 0 ? "Chủ nhật" : `Thứ ${n + 1}`;
}

function dayMonth(day: string): string {
  const [, m, d] = day.split("-");
  return `${d}/${m}`;
}

/**
 * Wireframe 1.5, shown inside the agent chat: pick a day, get the times that fit the seller's availability,
 * send the request (guests sign up right here first). With `reschedule`, the chosen time is proposed
 * as the new time of that confirmed viewing instead.
 */
export function ViewingScheduler({
  propertyId,
  reschedule,
  onBooked,
  onBack,
}: {
  propertyId: number;
  reschedule?: Booking;
  onBooked: (b: Booking) => void;
  onBack?: () => void;
}) {
  const queryClient = useQueryClient();
  const days = Array.from({ length: DAYS_AHEAD }, (_, i) => vnToday(i + 1));
  const [page, setPage] = useState(0);
  const [day, setDay] = useState(days[0]);
  const [chosen, setChosen] = useState<{
    start: string;
    end: string;
    fromProposals: boolean;
  } | null>(null);
  const [note, setNote] = useState("");
  // Guests confirm first, then sign up; the request is sent right after
  const { user } = useAuth();
  const [askSignup, setAskSignup] = useState(false);

  const windows: TimeWindow[] = [
    { start_at: vnIso(day, DAY_FROM), end_at: vnIso(day, DAY_TO) },
  ];

  const property = useProperty(propertyId);

  const times = useQuery({
    queryKey: ["viewing-times", propertyId, day],
    queryFn: () =>
      call(
        api.POST("/api/v1/properties/{property_id}/viewing-times", {
          params: { path: { property_id: propertyId } },
          body: { windows },
        }),
      ),
  });

  const book = useMutation({
    mutationFn: () =>
      reschedule
        ? call(
            api.POST("/api/v1/bookings/{booking_id}/reschedule", {
              params: { path: { booking_id: reschedule.id } },
              body: { start_at: chosen!.start },
            }),
          )
        : call(
            api.POST("/api/v1/bookings", {
              body: {
                property_id: propertyId,
                start_at: chosen!.start,
                // Alternatives lie outside the buyer's window, so no window is sent for them
                buyer_windows: chosen!.fromProposals ? windows : [],
                note: note.trim() || null,
              },
            }),
          ),
    onSuccess: (booking) => {
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
      onBooked(booking);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "SLOT_UNAVAILABLE") {
        setChosen(null);
        times.refetch();
      }
    },
  });

  function pickDay(d: string) {
    setDay(d);
    setChosen(null);
  }

  const proposals = times.data?.proposals ?? [];
  const alternatives = times.data?.alternatives ?? [];
  const visible = days.slice(
    page * DAYS_PER_PAGE,
    page * DAYS_PER_PAGE + DAYS_PER_PAGE,
  );
  const lastPage = Math.ceil(days.length / DAYS_PER_PAGE) - 1;

  return (
    <div className="w-full max-w-xl">
      <section
        className="card space-y-5 p-4 shadow-sm sm:p-5"
        aria-label={reschedule ? "Chọn giờ mới" : "Chọn lịch xem nhà"}
      >
        <div>
          {onBack && <BackButton onClick={onBack}>Quay lại</BackButton>}
          <h3 className="mt-1 text-lg font-bold">
            {reschedule ? "Chọn giờ mới" : "Chọn lịch xem nhà"}
          </h3>
          <p className="mt-1 text-sm text-muted">
            {reschedule
              ? `Lịch hiện tại: ${formatTimeRange(reschedule.start_at, reschedule.end_at)}. ` +
                (reschedule.status === "REQUESTED"
                  ? "Chủ căn chưa trả lời nên yêu cầu sẽ chuyển ngay sang giờ mới, vẫn chờ chủ căn xác nhận."
                  : "Lịch cũ giữ nguyên cho tới khi chủ căn đồng ý giờ mới.")
              : "AI sẽ gợi ý các khung giờ phù hợp dựa trên lịch của chủ căn."}
          </p>
          {property.data && (
            <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <span className="font-semibold">{property.data.unit_code}</span> ·{" "}
              {property.data.project_name} ·{" "}
              {formatVnd(property.data.price_vnd)}
            </p>
          )}
        </div>

        <div
          className="flex items-center gap-2"
          role="group"
          aria-label="Chọn ngày"
        >
          <button
            type="button"
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-slate-100 disabled:opacity-30"
            aria-label="Ngày trước"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeftIcon />
          </button>
          <div className="grid flex-1 grid-cols-3 gap-2">
            {visible.map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={day === d}
                onClick={() => pickDay(d)}
                className={`rounded-xl border px-2 py-2.5 text-center ${
                  day === d
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-line bg-white hover:border-brand-500"
                }`}
              >
                <span className="block text-sm font-semibold">
                  {weekday(d)}
                </span>
                <span className="block text-xs text-muted">{dayMonth(d)}</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-slate-100 disabled:opacity-30"
            aria-label="Ngày sau"
            disabled={page === lastPage}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRightIcon />
          </button>
        </div>

        <div>
          <h2 className="mb-3 font-semibold">
            {proposals.length > 0 || !times.data
              ? "Khung giờ đề xuất"
              : "Giờ trống gần nhất của chủ căn"}
          </h2>
          {times.isPending && <Spinner label="AI đang khớp lịch..." />}
          {times.isError && (
            <ErrorBox error={times.error} onRetry={() => times.refetch()} />
          )}
          {times.data &&
            proposals.length === 0 &&
            alternatives.length === 0 && (
              <Notice tone="warning">
                Chủ căn chưa có giờ trống trong 2 tuần tới. Hãy nhờ Trợ lý AI
                chuyển yêu cầu cho bộ phận hỗ trợ.
              </Notice>
            )}
          {times.data && proposals.length === 0 && alternatives.length > 0 && (
            <p className="mb-3 text-sm text-muted">
              Chủ căn không trống ngày {dayMonth(day)}. Bạn có thể chọn một giờ
              khác dưới đây:
            </p>
          )}

          {proposals.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {proposals.map((o) => (
                <TimeButton
                  key={o.start_at}
                  label={timeOf(o.start_at)}
                  title={formatTimeRange(o.start_at, o.end_at)}
                  active={chosen?.start === o.start_at}
                  onClick={() =>
                    setChosen({
                      start: o.start_at,
                      end: o.end_at,
                      fromProposals: true,
                    })
                  }
                />
              ))}
            </div>
          )}
          {proposals.length === 0 && alternatives.length > 0 && (
            <div className="grid gap-2 sm:grid-cols-2">
              {alternatives.map((o) => (
                <TimeButton
                  key={o.start_at}
                  label={formatTimeRange(o.start_at, o.end_at)}
                  active={chosen?.start === o.start_at}
                  onClick={() =>
                    setChosen({
                      start: o.start_at,
                      end: o.end_at,
                      fromProposals: false,
                    })
                  }
                />
              ))}
            </div>
          )}
        </div>

        {chosen && (
          <p className="flex items-center gap-2 rounded-xl border border-line bg-slate-50 px-4 py-3 text-sm">
            <ClockIcon className="size-4 text-brand-600" />
            Thời gian xem dự kiến:{" "}
            <strong>{formatTimeRange(chosen.start, chosen.end)}</strong>
          </p>
        )}

        {!reschedule && (
          <div>
            <label htmlFor={`note-${propertyId}`} className="label">
              Ghi chú cho chủ căn (không bắt buộc)
            </label>
            <textarea
              id={`note-${propertyId}`}
              rows={2}
              maxLength={1000}
              className="input"
              placeholder="VD: Đi cùng 2 người"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        )}

        {book.isError && <ErrorBox error={book.error} />}
        {book.error instanceof ApiError &&
          book.error.code === "SLOT_UNAVAILABLE" && (
            <p className="text-xs text-muted">
              Giờ này vừa có người đặt — danh sách giờ đã được cập nhật, hãy
              chọn giờ khác.
            </p>
          )}

        <button
          type="button"
          className="btn-primary w-full rounded-xl py-3 text-base"
          disabled={!chosen || book.isPending}
          onClick={() =>
            user?.role === "CUSTOMER" ? book.mutate() : setAskSignup(true)
          }
        >
          {book.isPending
            ? "Đang gửi..."
            : !chosen
              ? "Chọn một khung giờ"
              : reschedule
                ? reschedule.status === "REQUESTED"
                  ? "Đổi sang giờ này"
                  : "Gửi đề nghị đổi giờ"
                : "Gửi yêu cầu xem nhà"}
        </button>
        {askSignup && chosen && user?.role !== "CUSTOMER" && (
          <GuestSignup onDone={() => book.mutate()} />
        )}
        <p className="text-center text-xs text-muted">
          Lịch chỉ có hiệu lực khi chủ căn xác nhận.
        </p>
      </section>
    </div>
  );
}

function TimeButton({
  label,
  title,
  active,
  onClick,
}: {
  label: string;
  title?: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-xl border px-3 py-3 text-sm font-medium ${
        active
          ? "border-brand-600 bg-brand-600 text-white"
          : "border-line bg-white hover:border-brand-500"
      }`}
    >
      {label}
    </button>
  );
}
