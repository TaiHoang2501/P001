import { API_BASE, ApiError } from "./client";

/**
 * Developer-only API (/api/v1/admin, header X-Admin-Token = ADMIN_API_TOKEN). It is hidden from the OpenAPI schema,
 * so it has no generated types: the shapes below mirror src/services/dev_metrics.py and assistant_control.py.
 */

export interface AssistantControl {
  enabled: boolean;
  message: string | null;
  hotline: string;
  reason: string | null;
  updated_at: string | null;
  updated_by: number | null;
}

export interface DevMetrics {
  days: number;
  generated_at: string;
  assistant: AssistantControl;
  ai: {
    turns: number;
    guest_turns: number;
    errors: number;
    error_rate: number;
    conversations: number;
    latency_p50_ms: number | null;
    latency_p95_ms: number | null;
    prompt_tokens: number;
    completion_tokens: number;
    llm_calls: number;
    tool_calls: number;
    daily: { date: string; turns: number; errors: number }[];
    tools: { name: string; calls: number; failed: number }[];
    error_types: { type: string; count: number }[];
    recent_errors: {
      trace_id: string;
      created_at: string;
      error_type: string | null;
      error_message: string | null;
      guest: boolean;
      latency_ms: number;
    }[];
  };
  guardrails: { turns_flagged: number; blocked_inputs: number; flags: { flag: string; count: number }[] };
  business: {
    bookings_by_status: Record<string, number>;
    deals_by_status: Record<string, number>;
    properties_by_status: Record<string, number>;
    open_escalations_by_type: Record<string, number>;
    users_by_role: Record<string, number>;
  };
}

export async function adminCall<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/v1/admin${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Admin-Token": token, ...init.headers },
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Network error", 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(error?.code ?? `HTTP_${response.status}`, error?.message ?? "Request failed", response.status);
  }
  return body as T;
}
