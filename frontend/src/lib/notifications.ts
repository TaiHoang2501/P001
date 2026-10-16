import type { Role } from "../api/types";
import { jumpParam } from "./jump";

/**
 * Notifications the buyer gets as the assistant's own messages in the chat (follow-ups, new matching homes, a time
 * taken by someone else, times the owner suggested, a request that expired).
 */
export const CHAT_EVENTS = new Set([
  "AGENT_FOLLOWUP",
  "AGENT_NEW_MATCH",
  "VIEWING_SUPERSEDED",
  "VIEWING_TIMES_SUGGESTED",
  "VIEWING_EXPIRED",
  "PROPERTY_SOLD",
]);

type Note = {
  event_type: string;
  sent_at?: string | null;
  booking_id?: number | null;
  payload?: Record<string, unknown> | null;
};

/**
 * Where a notification leads, in the reader's own area: the very item it is about (that viewing request, listing,
 * support case or chat message), which then flashes (see useJumpFlash). Null when it is about nothing to open.
 */
export function notificationTarget(n: Note, role: Role): string | null {
  const payload = (n.payload ?? {}) as { property_id?: number; escalation_id?: number };
  const booking = n.booking_id;
  const jump = jumpParam();
  switch (role) {
    case "OWNER":
      if (booking) return `/owner/bookings?booking=${booking}&${jump}`;
      if (n.event_type.startsWith("LISTING_"))
        return payload.property_id ? `/owner?property=${payload.property_id}&${jump}` : "/owner";
      if (n.event_type.startsWith("OWNERSHIP_") && payload.escalation_id)
        return `/owner/verify?case=${payload.escalation_id}&${jump}`;
      if (n.event_type.startsWith("SELLER_") || n.event_type.startsWith("OWNERSHIP_")) return "/owner/verify";
      return null;
    case "CUSTOMER":
      // Always the "Hoạt động" page: the card of the viewing it is about (also for the assistant's messages about
      // a viewing); a notice about no viewing in particular (e.g. new matching homes) opens the page itself
      // `at`: when it was sent, so the page lights up the very event in its history (recorded at the same moment)
      return booking
        ? `/buyer/activity?booking=${booking}${n.sent_at ? `&at=${encodeURIComponent(n.sent_at)}` : ""}&${jump}`
        : "/buyer/activity";
    case "INVESTOR_OPERATOR":
      if (n.event_type.startsWith("ESCALATION_"))
        return payload.escalation_id ? `/operator/escalations?case=${payload.escalation_id}&${jump}` : "/operator/escalations";
      if (booking) return `/operator/bookings?booking=${booking}&${jump}`;
      return null;
    default:
      return null;
  }
}

/** A group of notifications in the bell (filter chips), by what the reader has to do or know. */
export type NoteGroup = { key: string; label: string; events: string[] };

// Event names; "X_*" matches every event starting with "X_"
const GROUPS: Partial<Record<Role, NoteGroup[]>> = {
  OWNER: [
    { key: "answer", label: "Cần bạn xác nhận", events: ["VIEWING_REQUESTED", "VIEWING_REQUEST_UPDATED"] },
    { key: "reschedule", label: "Xin đổi lịch", events: ["RESCHEDULE_REQUESTED"] },
    { key: "after", label: "Sau buổi xem", events: ["VIEWING_OUTCOME_DUE", "BUYER_INTERESTED", "VIEWING_OUTCOME_RECORDED"] },
    { key: "viewings", label: "Lịch xem", events: ["VIEWING_CANCELLED", "REMINDER_*", "HOLD_*", "VIEWING_CONFIRMED"] },
    { key: "listings", label: "Tin đăng & sổ đỏ", events: ["LISTING_*", "OWNERSHIP_*", "SELLER_*"] },
    { key: "support", label: "Hỗ trợ", events: ["ESCALATION_*"] },
  ],
  CUSTOMER: [
    {
      key: "confirmed",
      label: "Lịch đã xác nhận",
      events: ["VIEWING_CONFIRMED", "RESCHEDULE_APPROVED", "RESCHEDULE_CONFIRMED", "REMINDER_*", "HOLD_*"],
    },
    { key: "suggested", label: "Chủ căn đề xuất giờ khác", events: ["VIEWING_TIMES_SUGGESTED"] },
    {
      key: "assistant",
      label: "Trợ lý AI gợi ý",
      events: ["AGENT_FOLLOWUP", "AGENT_NEW_MATCH", "VIEWING_SUPERSEDED", "VIEWING_EXPIRED", "PROPERTY_SOLD"],
    },
    {
      key: "declined",
      label: "Bị từ chối / hủy",
      events: ["VIEWING_REJECTED", "VIEWING_CANCELLED", "RESCHEDULE_DECLINED", "RESCHEDULE_LAPSED"],
    },
    { key: "after", label: "Sau buổi xem", events: ["VIEWING_COMPLETED", "VIEWING_NO_SHOW", "VIEWING_OUTCOME_RECORDED"] },
    { key: "support", label: "Hỗ trợ", events: ["ESCALATION_*"] },
  ],
  // The operator's notifications are all "a new case": grouped by the kind of case instead (see caseGroupOf)
  INVESTOR_OPERATOR: [
    { key: "SELLER_NO_RESPONSE", label: "Chủ căn chưa phản hồi", events: [] },
    { key: "NO_COMMON_SLOT", label: "Không có giờ xem chung", events: [] },
    { key: "OWNERSHIP_SUPPORT", label: "Hỗ trợ sổ đỏ / sổ hồng", events: [] },
    { key: "VIEWING_DISPUTE", label: "Tranh chấp buổi xem", events: [] },
    { key: "OTHER", label: "Khách cần hỗ trợ", events: [] },
    { key: "incidents", label: "Sự cố khác", events: [] },
  ],
};

// Older notifications carry the kind of case only in their title ("Ca mới: <label>")
const CASE_BY_TITLE: Record<string, string> = {
  "Chủ căn chưa phản hồi": "SELLER_NO_RESPONSE",
  "Không có giờ xem chung": "NO_COMMON_SLOT",
  "Hỗ trợ xác thực sổ đỏ / sổ hồng": "OWNERSHIP_SUPPORT",
  "Tranh chấp kết quả buổi xem": "VIEWING_DISPUTE",
  "Khách cần hỗ trợ": "OTHER",
};
const CASE_LABEL: Record<string, string> = Object.fromEntries(Object.entries(CASE_BY_TITLE).map(([label, type]) => [type, label]));

/** A notification's title as shown; older ones named the kind of case by its code ("Cần xử lý: SELLER_NO_RESPONSE"). */
export function noteTitle(n: { title: string }): string {
  const m = /^Cần xử lý: ([A-Z_]+)$/.exec(n.title);
  return m ? `Ca mới: ${CASE_LABEL[m[1]] ?? "Sự cố hệ thống"}` : n.title;
}
const CASE_GROUPS = new Set(["SELLER_NO_RESPONSE", "NO_COMMON_SLOT", "OWNERSHIP_SUPPORT", "VIEWING_DISPUTE", "OTHER"]);

/** The operator's group for a notification: the kind of case it opens (system failures, conflicts... together). */
function caseGroupOf(n: GroupedNote): string {
  if (!n.event_type.startsWith("ESCALATION_")) return "other";
  const type =
    ((n.payload ?? {}) as { escalation_type?: string }).escalation_type ??
    CASE_BY_TITLE[(n.title ?? "").replace(/^(Ca mới|Cần xử lý): /, "")];
  return type && CASE_GROUPS.has(type) ? type : "incidents";
}
const OTHER: NoteGroup = { key: "other", label: "Khác", events: [] };

function matches(group: NoteGroup, eventType: string): boolean {
  return group.events.some((e) => (e.endsWith("_*") ? eventType.startsWith(e.slice(0, -1)) : e === eventType));
}

/** The groups for this role, plus "Khác" for anything that fits none. */
export function noteGroups(role: Role): NoteGroup[] {
  return [...(GROUPS[role] ?? []), OTHER];
}

type GroupedNote = { event_type: string; title?: string | null; payload?: Record<string, unknown> | null };

/** Which of the role's groups a notification belongs to. */
export function noteGroupOf(n: GroupedNote, role: Role): string {
  if (role === "INVESTOR_OPERATOR") return caseGroupOf(n);
  return (GROUPS[role] ?? []).find((g) => matches(g, n.event_type))?.key ?? OTHER.key;
}
