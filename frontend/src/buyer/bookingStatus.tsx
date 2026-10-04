import type { Booking, Deal } from "../api/types";
import { formatDateTime } from "../lib/format";
import { CheckIcon } from "./icons";

/** The deal's path as the buyer sees it (wireframe 1.6). */
export const STEPS = ["Gửi yêu cầu", "Chờ chủ căn xác nhận", "Xác nhận lịch", "Xem nhà", "Quan tâm", "Gửi yêu cầu mua", "Hoàn tất"];

export const ENDED = new Set<Booking["status"]>(["REJECTED", "CANCELLED", "NO_SHOW"]);
export const CANCELLABLE = new Set<Booking["status"]>(["REQUESTED", "CONFIRMED", "RESCHEDULE_REQUESTED"]);

/** How far the deal got along STEPS (index of the step in progress; STEPS.length when done). */
export function progressOf(booking: Booking, deal?: Deal): number {
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

export function endedLabel(b: Booking): string {
  return b.status === "REJECTED" ? "chủ căn từ chối" : b.status === "NO_SHOW" ? "vắng mặt" : "đã hủy/đóng";
}

export function StatusTimeline({ booking, deal, compact = false }: { booking: Booking; deal?: Deal; compact?: boolean }) {
  const progress = progressOf(booking, deal);
  return (
    <ol>
      {STEPS.map((step, i) => {
        const done = i < progress;
        const current = i === progress;
        return (
          <li key={step} className={`relative flex items-start gap-3 last:pb-0 ${compact ? "pb-2.5" : "pb-4"}`}>
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
            {i === 0 && <span className="text-xs text-muted">{formatDateTime(booking.created_at)}</span>}
          </li>
        );
      })}
    </ol>
  );
}
