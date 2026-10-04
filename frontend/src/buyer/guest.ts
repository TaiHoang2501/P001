import { api, call } from "../api/client";
import type { User } from "../api/types";

/**
 * New buyers chat as guests (no account) until they send a viewing request; then they sign up with phone + OTP.
 * The choice and the guest conversation live in sessionStorage, i.e. only in this browser tab.
 */
const GUEST_KEY = "bookingbot.buyer.guest";
export const GUEST_CHAT_KEY = "bookingbot.chat.guest";

export function chatStorageKey(userId: number | null): string {
  return userId === null ? GUEST_CHAT_KEY : `bookingbot.chat.${userId}`;
}

export function isGuest(): boolean {
  try {
    return sessionStorage.getItem(GUEST_KEY) === "1";
  } catch {
    return false;
  }
}

export function startGuest(): void {
  try {
    sessionStorage.setItem(GUEST_KEY, "1");
  } catch {
    // Storage blocked: guest mode lasts for this page view only
  }
}

export function endGuest(): void {
  try {
    sessionStorage.removeItem(GUEST_KEY);
  } catch {
    // ignore
  }
}

/**
 * Right after a guest signs up or signs in: continue their guest chat under the account, then leave guest mode.
 * The messages shown in this tab move at once (so the chat page opens on them); the agent's memory of the
 * conversation moves on the server in the background.
 */
export async function adoptGuestChat(user: User): Promise<void> {
  endGuest();
  if (user.role !== "CUSTOMER") return;
  let conversationId: string;
  try {
    const raw = sessionStorage.getItem(GUEST_CHAT_KEY);
    if (!raw) return;
    conversationId = (JSON.parse(raw) as { id: string }).id;
    const target = chatStorageKey(user.id);
    if (!sessionStorage.getItem(target)) sessionStorage.setItem(target, raw);
    sessionStorage.removeItem(GUEST_CHAT_KEY);
  } catch {
    return;
  }
  try {
    await call(api.POST("/api/v1/chat/guest/{conversation_id}/claim", { params: { path: { conversation_id: conversationId } } }));
  } catch {
    // The account still works; the agent just continues without the guest context
  }
}
