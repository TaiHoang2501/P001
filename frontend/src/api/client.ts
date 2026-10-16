import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";
import type { ChatResponse, Notification } from "./types";

/**
 * Typed API client generated from the FastAPI OpenAPI spec.
 * Regenerate types after backend changes: `npm run gen:api` (backend must be running).
 */
// No trailing slash: VITE_API_URL may be set as "https://host/", and paths already start with "/"
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

export const api = createClient<paths>({ baseUrl: API_BASE });

/** Wake the backend as the page opens, so a server that went idle is up by the time the user acts. */
export function warmUpApi() {
  fetch(`${API_BASE}/health`).catch(() => undefined);
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAuthToken(value: string | null) {
  token = value;
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ response, request }) {
    // Expired/invalid session: log out, but not for the login call itself
    if (response.status === 401 && token && !request.url.includes("/auth/login")) onUnauthorized?.();
    return response;
  },
};
api.use(authMiddleware);

/** Business error returned by the backend: { error: { code, message, details } } */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

const FRIENDLY: Record<string, string> = {
  UNAUTHENTICATED: "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.",
  INVALID_CREDENTIALS: "Thông tin đăng nhập hoặc mã OTP không đúng.",
  RATE_LIMITED: "Bạn yêu cầu mã quá nhiều lần, vui lòng thử lại sau ít phút.",
  SELLER_UNVERIFIED: "Chủ căn chưa được Chủ đầu tư xác thực.",
  AGENT_UNAVAILABLE: "Trợ lý AI đang tạm thời gián đoạn, vui lòng thử lại sau.",
  STORAGE_UNAVAILABLE: "Không tải được tệp lên lúc này, vui lòng thử lại sau.",
  FORBIDDEN: "Bạn không có quyền thực hiện thao tác này.",
  NOT_FOUND: "Không tìm thấy dữ liệu.",
  ALREADY_EXISTS: "Dữ liệu đã tồn tại.",
  STATE_CONFLICT: "Trạng thái hiện tại không cho phép thao tác này.",
  SLOT_UNAVAILABLE: "Khung giờ này vừa có người đặt. Vui lòng chọn khung giờ khác.",
  OWNERSHIP_NOT_MATCHED: "Họ tên hoặc mã số sổ đỏ / sổ hồng không khớp với dữ liệu của Chủ đầu tư.",
  OTP_INVALID: "Mã OTP không đúng hoặc đã hết hạn.",
  PHONE_IN_USE: "Số điện thoại này đã tồn tại trên hệ thống. Vui lòng nhập số điện thoại khác.",
  BUSINESS_RULE_VIOLATION: "Thao tác không hợp lệ.",
  VALIDATION_ERROR: "Dữ liệu nhập chưa hợp lệ.",
  NETWORK_ERROR: "Không kết nối được máy chủ.",
  TIMEOUT: "Máy chủ phản hồi quá lâu. Vui lòng bấm thử lại.",
};

// The backend's rule messages are English (for logs and the API); what a user reads is Vietnamese. By the message's
// start, so messages with numbers in them match too; anything not listed falls back to the generic sentence
const RULES_VI: [string, string][] = [
  ["The seller is not available at this time", "Chủ căn không rảnh vào giờ này. Hãy chọn một giờ trống của căn."],
  ["Book a viewing at least", "Giờ xem cần cách hiện tại ít nhất 2 tiếng. Hãy chọn giờ muộn hơn."],
  ["This viewing time has already started", "Giờ xem này đã qua. Hãy chọn giờ khác."],
  ["This viewing's time has already come", "Buổi xem đã tới giờ nên không đổi giờ được nữa."],
  ["Viewing has already started", "Buổi xem đã tới giờ nên không thực hiện được thao tác này."],
  ["Viewing time has already passed", "Giờ xem đã qua."],
  ["Viewing has not started yet", "Buổi xem chưa diễn ra."],
  ["Slot must start in the future", "Khung giờ phải ở tương lai."],
  ["This slot overlaps an existing slot", "Khung giờ này trùng với một khung giờ đã có của căn."],
  ["Suggest times from your own free viewing times", "Chỉ đề xuất được các giờ trống của chính bạn (cách hiện tại ít nhất 2 tiếng)."],
  ["Other times can be suggested for a new request only", "Chỉ đề xuất giờ khác được cho yêu cầu chưa trả lời."],
  ["These details come from the red book", "Thông tin này lấy từ sổ đỏ / sổ hồng, không sửa được."],
  ["Verify ownership of this home", "Hãy xác thực sổ đỏ / sổ hồng của căn trước khi đăng bán."],
  ["Verify the red book of this home", "Hãy xác thực sổ đỏ / sổ hồng của căn trước khi gửi duyệt."],
  ["This red book is registered to another phone", "Sổ này đăng ký số điện thoại khác. Hãy gửi yêu cầu hỗ trợ nếu bạn bán thay chủ sở hữu."],
  ["Upload the photo; links to other sites", "Hãy tải ảnh lên; không dùng được đường link ảnh từ trang khác."],
  ["A listing can have at most", "Tin đăng đã đủ số ảnh tối đa."],
  ["Only JPEG, PNG or WebP photos", "Chỉ tải được ảnh JPEG, PNG hoặc WebP."],
  ["Photos must be at most", "Ảnh quá lớn."],
  ["File must be between", "Tệp rỗng hoặc quá lớn."],
  ["The file is empty", "Tệp rỗng."],
  ["Attach documents uploaded from your device", "Hãy đính kèm giấy tờ tải lên từ máy của bạn."],
  ["Choose a buyer who viewed this home", "Chỉ chọn được người mua đã xem căn trên BookingBot, hoặc chọn người mua ngoài BookingBot."],
  ["This home is no longer open for viewings", "Căn này không còn nhận lịch xem."],
  ["Only a listing on the market can be taken down", "Chỉ gỡ được tin đang bán."],
];

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    // Rule errors: the Vietnamese sentence for the backend's message, or a generic one (never the English text)
    if (err.code === "BUSINESS_RULE_VIOLATION" || err.code === "ALREADY_EXISTS" || err.code === "STATE_CONFLICT") {
      const vi = RULES_VI.find(([en]) => err.message.startsWith(en));
      if (vi) return vi[1];
      // Some rule messages are already Vietnamese (they carry its accented letters): shown as they are
      if (err.code === "BUSINESS_RULE_VIOLATION" && /[ăâđêôơưạ-ỹĂÂĐÊÔƠƯẠ-Ỹ]/.test(err.message)) return err.message;
    }
    if (err.code === "BUSINESS_RULE_VIOLATION" || err.code === "ALREADY_EXISTS") return FRIENDLY[err.code];
    // Withdraw / mark as sold while viewings are still open
    const active = err.details.active;
    if (err.code === "STATE_CONFLICT" && typeof active === "number")
      return `Căn còn ${active} lịch xem đang chờ hoặc đã hẹn. Hãy trả lời các yêu cầu đang chờ; lịch đã xác nhận thì ghi nhận kết quả sau buổi xem, hoặc nhờ Chủ đầu tư hủy giúp nếu cần.`;
    // Sign-in code: what to do next
    if (err.code === "INVALID_CREDENTIALS" && err.details.new_code_needed === true)
      return "Mã này không còn dùng được (nhập sai quá nhiều lần hoặc đã hết hạn). Bấm “Gửi lại mã” để nhận mã mới.";
    const left = err.details.attempts_left;
    if (err.code === "INVALID_CREDENTIALS" && typeof left === "number") return `Mã không đúng. Còn ${left} lần thử.`;
    // Chat messages to the AI assistant (rate limited per buyer / guest IP, and for all guests together per day)
    if (err.code === "RATE_LIMITED" && err.details.scope === "chat_guest_daily")
      return "Trợ lý đang nhận quá nhiều tin nhắn từ khách chưa đăng nhập. Vui lòng đăng nhập để tiếp tục trò chuyện.";
    const waitSeconds = err.details.retry_after_seconds;
    if (err.code === "RATE_LIMITED" && err.details.scope === "chat" && typeof waitSeconds === "number")
      return `Bạn gửi tin nhắn hơi nhanh. Vui lòng thử lại sau ${waitSeconds < 60 ? `${waitSeconds} giây` : `${Math.ceil(waitSeconds / 60)} phút`}.`;
    const wait = err.details.retry_after_minutes;
    if (err.code === "RATE_LIMITED" && typeof wait === "number")
      return `Bạn đã yêu cầu mã quá nhiều lần mà chưa nhập. Vui lòng thử lại sau ${wait} phút.`;
    return FRIENDLY[err.code] ?? err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

function toApiError(body: unknown, status: number): ApiError {
  if (body && typeof body === "object") {
    const b = body as { error?: { code: string; message: string; details?: Record<string, unknown> }; detail?: unknown };
    if (b.error) return new ApiError(b.error.code, b.error.message, status, b.error.details ?? {});
    if (Array.isArray(b.detail)) {
      const first = b.detail[0] as { msg?: string; loc?: unknown[] } | undefined;
      const field = first?.loc?.slice(1).join(".");
      return new ApiError("VALIDATION_ERROR", `${field ? field + ": " : ""}${first?.msg ?? "invalid"}`, status, {
        errors: b.detail,
      });
    }
  }
  return new ApiError("HTTP_" + status, `Request failed (${status})`, status);
}

/** Await an openapi-fetch call and return its data, or throw ApiError. */
export async function call<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await request;
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") throw new ApiError("TIMEOUT", "Timed out", 0);
    throw new ApiError("NETWORK_ERROR", "Network error", 0);
  }
  if (!result.response.ok) throw toApiError(result.error, result.response.status);
  return result.data as T;
}

export interface ChatStreamHandlers {
  /** A piece of the reply, as the model writes it */
  onToken: (text: string) => void;
  /** The agent is calling tools; text streamed before was only a preface */
  onTools: (names: string[]) => void;
  /** The guardrail changed the reply: show this text instead of what was streamed so far */
  onReplace?: (text: string) => void;
}

/**
 * The agent's reply as Server-Sent Events (POST /chat/stream, /chat/guest/stream): pieces of text arrive while
 * the model writes; resolves with the final ChatResponse (cards, bookings) from the `done` event.
 */
export async function streamChat(
  path: "/api/v1/chat/stream" | "/api/v1/chat/guest/stream",
  body: { message: string; conversation_id: string },
  handlers: ChatStreamHandlers,
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Network error", 0);
  }
  if (!response.ok || !response.body) {
    if (response.status === 401 && token) onUnauthorized?.();
    throw toApiError(await response.json().catch(() => null), response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    let chunk: ReadableStreamReadResult<Uint8Array>;
    try {
      chunk = await reader.read();
    } catch {
      throw new ApiError("NETWORK_ERROR", "Network error", 0);
    }
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    // Events are separated by a blank line: "event: <name>\ndata: <json>"
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let name = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      const payload = data ? JSON.parse(data) : {};
      if (name === "token") handlers.onToken(payload.text);
      else if (name === "tools") handlers.onTools(payload.names);
      else if (name === "replace") handlers.onReplace?.(payload.text);
      else if (name === "error") throw new ApiError(payload.code, payload.message, 503);
      else if (name === "done") return payload as ChatResponse;
    }
  }
  // The connection closed before the reply was complete
  throw new ApiError("AGENT_UNAVAILABLE", "Stream ended early", 503);
}


/**
 * Live notifications (GET /notifications/stream, Server-Sent Events): `onNotification` for each new one as soon as
 * it is sent. Resolves with the cursor to reconnect with (`after`) when the server ends the stream after a few
 * minutes; rejects on a network error or when the session is gone (ApiError 401).
 */
export async function streamNotifications(
  onNotification: (n: Notification) => void,
  opts: { after?: string | null; signal?: AbortSignal; onReady?: () => void } = {},
): Promise<string | null> {
  const query = opts.after ? `?after=${encodeURIComponent(opts.after)}` : "";
  const response = await fetch(`${API_BASE}/api/v1/notifications/stream${query}`, {
    headers: { Accept: "text/event-stream", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    signal: opts.signal,
  });
  if (!response.ok || !response.body) {
    if (response.status === 401 && token) onUnauthorized?.();
    throw toApiError(await response.json().catch(() => null), response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let after: string | null = opts.after ?? null;
  for (;;) {
    const chunk = await reader.read();
    if (chunk.done) return after;
    buffer += decoder.decode(chunk.value, { stream: true });
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let name = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue; // ": ping" keep-alive
      const payload = JSON.parse(data);
      if (name === "ready") opts.onReady?.();
      else if (name === "notification") {
        after = payload.sent_at ?? after;
        onNotification(payload as Notification);
      } else if (name === "bye") return payload.after ?? after;
    }
  }
}
