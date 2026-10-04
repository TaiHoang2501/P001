import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";
import type { ChatResponse } from "./types";

/**
 * Typed API client generated from the FastAPI OpenAPI spec.
 * Regenerate types after backend changes: `npm run gen:api` (backend must be running).
 */
export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL ?? "" });

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
  OWNERSHIP_NOT_MATCHED: "Họ tên hoặc mã số sổ đỏ không khớp với dữ liệu của Chủ đầu tư.",
  OTP_INVALID: "Mã OTP không đúng hoặc đã hết hạn.",
  PHONE_IN_USE: "Số điện thoại này đã tồn tại trên hệ thống. Vui lòng nhập số điện thoại khác.",
  BUSINESS_RULE_VIOLATION: "Thao tác không hợp lệ.",
  VALIDATION_ERROR: "Dữ liệu nhập chưa hợp lệ.",
  NETWORK_ERROR: "Không kết nối được máy chủ.",
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    // Backend messages are English; prefer the Vietnamese text, keep backend detail for 4xx rule errors
    if (err.code === "BUSINESS_RULE_VIOLATION" || err.code === "ALREADY_EXISTS") return `${FRIENDLY[err.code]} (${err.message})`;
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
  } catch {
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
    response = await fetch(`${import.meta.env.VITE_API_URL ?? ""}${path}`, {
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
      else if (name === "error") throw new ApiError(payload.code, payload.message, 503);
      else if (name === "done") return payload as ChatResponse;
    }
  }
  // The connection closed before the reply was complete
  throw new ApiError("AGENT_UNAVAILABLE", "Stream ended early", 503);
}
