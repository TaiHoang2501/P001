import type { Booking, Deal } from "../api/types";
import { formatDateTime, formatTimeRange } from "../lib/format";
import { CheckIcon } from "./icons";

/** The viewing's path as the buyer sees it. BookingBot helps book viewings; buying itself is out of its scope, so
 * the path ends with the buyer saying how they found the home. */
export const STEPS = ["Gửi yêu cầu", "Chờ chủ căn xác nhận", "Xác nhận lịch", "Xem nhà", "Cho biết cảm nhận"];
const FEEDBACK_STEP = 4;

export const ENDED = new Set<Booking["status"]>([
  "REJECTED",
  "CANCELLED",
  "NO_SHOW",
  "OWNER_ABSENT",
  "UNREPORTED",
  "EXPIRED",
]);
export const CANCELLABLE = new Set<Booking["status"]>(["REQUESTED", "CONFIRMED", "RESCHEDULE_REQUESTED"]);

/** How far the deal got along STEPS (index of the step in progress; STEPS.length when done). */
export function progressOf(booking: Booking, deal?: Deal): number {
  switch (deal?.status) {
    // The buyer has said how they found the home (or things went further): the whole path is done
    case "INTERESTED":
    case "NEGOTIATING":
    case "TRANSACTION_SUPPORT":
    case "COMPLETED":
      return STEPS.length;
    case "CLOSED":
      return booking.status === "COMPLETED" ? STEPS.length : 1;
    case "VIEWED":
      return FEEDBACK_STEP;
    default:
      break;
  }
  if (booking.status === "COMPLETED") return 4;
  // Asking for a new time keeps the confirmed viewing (and its QR) until the owner agrees
  if (booking.status === "CONFIRMED" || booking.status === "RESCHEDULE_REQUESTED") return 3;
  return 1;
}

export function endedLabel(b: Booking): string {
  // Closed by BookingBot, not by the owner's "no"
  if (b.rejection_reason === "Căn đã được bán" || (b.status === "CANCELLED" && b.sold_to_other)) return "căn đã được bán";
  if (b.rejection_reason === "Tin đăng đang tạm ngừng") return "tin đăng đang tạm ngừng";
  if (b.status === "REJECTED" && b.closed_by_system) return "chủ căn đã nhận lịch xem khác vào giờ này";
  if (b.status === "REJECTED") return "chủ căn từ chối";
  if (b.status === "NO_SHOW") return "ghi nhận bạn không đến";
  if (b.status === "OWNER_ABSENT") return "chủ căn vắng mặt";
  if (b.status === "UNREPORTED") return "không ai ghi nhận kết quả";
  if (b.status === "EXPIRED") return "chủ căn chưa trả lời trước giờ xem";
  return "đã hủy/đóng";
}

/** The steps shown for this viewing: while a new time is asked for, an extra step sits between the confirmed
 * time (still held) and the viewing, so it is clear what the owner is being asked now. */
function stepsOf(booking: Booking, deal?: Deal): { label: string; note?: string; done: boolean; current: boolean }[] {
  const progress = progressOf(booking, deal);
  const steps = STEPS.map((label, i) => ({ label, note: undefined as string | undefined, done: i < progress, current: i === progress }));
  if (booking.status === "CONFIRMED" || booking.status === "RESCHEDULE_REQUESTED") {
    steps[2].note = formatTime(booking.start_at) + (booking.status === "RESCHEDULE_REQUESTED" ? " · vẫn đang giữ" : "");
  }
  // The buyer's answer after the viewing
  if (booking.status === "COMPLETED" && deal) {
    if (["INTERESTED", "NEGOTIATING", "TRANSACTION_SUPPORT", "COMPLETED"].includes(deal.status))
      steps[FEEDBACK_STEP].note = "Bạn quan tâm căn này";
    else if (deal.status === "CLOSED") steps[FEEDBACK_STEP].note = "Bạn thấy căn chưa phù hợp";
  }
  if (booking.status === "RESCHEDULE_REQUESTED" && booking.proposed_start_at) {
    steps[3].current = false; // "Xem nhà" waits until the owner answers
    steps.splice(3, 0, {
      label: "Chờ chủ căn đồng ý giờ mới",
      note: `Bạn xin đổi sang ${formatTime(booking.proposed_start_at)}`,
      done: false,
      current: true,
    });
  }
  return steps;
}

/** "14:00 Thứ 6, 16/10" */
function formatTime(iso: string): string {
  return formatTimeRange(iso, iso).split(" · ").reverse().join(" ");
}

export function StatusTimeline({ booking, deal, compact = false }: { booking: Booking; deal?: Deal; compact?: boolean }) {
  const steps = stepsOf(booking, deal);
  return (
    <ol>
      {steps.map((step, i) => {
        const { done, current } = step;
        // A new time asked for: its step stands out (violet, like the "Chờ xác nhận đổi lịch" label)
        const asking = current && step.label === "Chờ chủ căn đồng ý giờ mới";
        return (
          <li key={step.label} className={`relative flex items-start gap-3 last:pb-0 ${compact ? "pb-2.5" : "pb-4"}`}>
            {i < steps.length - 1 && (
              <span className={`absolute left-[9px] top-5 h-full w-0.5 ${done ? "bg-brand-600" : "bg-line"}`} aria-hidden="true" />
            )}
            <span
              className={`relative grid size-5 shrink-0 place-items-center rounded-full ${
                done
                  ? "bg-brand-600 text-white"
                  : asking
                    ? "border-2 border-violet-600 bg-violet-100"
                    : current
                      ? "border-2 border-brand-600 bg-white"
                      : "border-2 border-line bg-white"
              }`}
            >
              {done && <CheckIcon className="size-3" strokeWidth={3} />}
            </span>
            <span className={`flex-1 text-sm ${done || current ? "font-medium text-ink" : "text-muted"}`}>
              <span className={asking ? "text-violet-800" : undefined}>{step.label}</span>
              {current && <span className="sr-only"> (đang chờ)</span>}
              {step.note && (
                <span className={`block text-xs font-normal ${asking ? "text-violet-700" : "text-muted"}`}>{step.note}</span>
              )}
            </span>
            {i === 0 && <span className="text-xs text-muted">{formatDateTime(booking.created_at)}</span>}
          </li>
        );
      })}
    </ol>
  );
}
