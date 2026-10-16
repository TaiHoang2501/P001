import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { api, ApiError, call, streamNotifications } from "../api/client";
import type { Notification } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { noteTitle, notificationTarget } from "../lib/notifications";

const SHOW_MS = 8000;
const MAX_TOASTS = 4;

/**
 * Live pop-ups for every signed-in user (buyer, seller, investor/operator): each new notification (a viewing
 * request for the owner, the owner's answer for the buyer, a new case for the operator...) appears at once as a
 * bubble in the corner, like Facebook. Clicking it opens what it is about. The page's data refreshes at the same
 * time, so lists and counts update without reloading.
 */
export function LiveNotifications() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [toasts, setToasts] = useState<Notification[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  // One stream per signed-in account (a new one when the account or the part of the site changes)
  const account = user ? `${user.role}:${user.id}` : null;

  function dismiss(id: number) {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setToasts((all) => all.filter((t) => t.id !== id));
  }

  useEffect(() => {
    if (!account) return;
    const abort = new AbortController();
    let after: string | null = null;
    let wait = 2000;

    function show(n: Notification) {
      setToasts((all) => [n, ...all.filter((t) => t.id !== n.id)].slice(0, MAX_TOASTS));
      timers.current.set(n.id, setTimeout(() => dismiss(n.id), SHOW_MS));
      // Lists, counts and the bell pick up the change without a reload
      void queryClient.invalidateQueries();
    }

    async function run() {
      while (!abort.signal.aborted) {
        try {
          after = await streamNotifications(show, {
            after,
            signal: abort.signal,
            onReady: () => {
              wait = 2000;
            },
          });
        } catch (err) {
          if (abort.signal.aborted) return;
          // Signed out (the client handles it) or not allowed: no stream
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return;
          // Network or server hiccup: try again, waiting longer each time (up to 30 s)
          await new Promise((r) => setTimeout(r, wait));
          wait = Math.min(wait * 2, 30_000);
        }
      }
    }
    void run();
    const pending = timers.current;
    return () => {
      abort.abort();
      pending.forEach(clearTimeout);
      pending.clear();
      setToasts([]);
    };
  }, [account, queryClient]);

  if (!user || toasts.length === 0) return null;

  function open(n: Notification) {
    dismiss(n.id);
    void call(api.POST("/api/v1/notifications/{notification_id}/read", { params: { path: { notification_id: n.id } } }))
      .then(() => queryClient.invalidateQueries({ queryKey: ["notifications"] }))
      .catch(() => undefined);
    const target = notificationTarget(n, user!.role);
    if (target) navigate(target);
  }

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 top-4 z-50 flex flex-col items-end gap-3 sm:left-auto sm:right-4 sm:w-96"
    >
      {toasts.map((n) => (
        <div
          key={n.id}
          role="status"
          className="pointer-events-auto flex w-full animate-rise-in items-start gap-3 rounded-2xl bg-white p-4 shadow-2xl shadow-slate-900/15 ring-1 ring-line"
        >
          <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-brand-600 text-white" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-5">
              <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" strokeLinecap="round" />
            </svg>
          </span>
          <button type="button" onClick={() => open(n)} className="min-w-0 flex-1 text-left">
            <p className="text-sm font-semibold text-ink">{noteTitle(n)}</p>
            {n.body && <p className="mt-0.5 line-clamp-2 text-sm text-muted">{n.body}</p>}
            <p className="mt-1 text-xs font-medium text-brand-700">Vừa xong · Bấm để xem</p>
          </button>
          <button
            type="button"
            onClick={() => dismiss(n.id)}
            aria-label="Đóng thông báo"
            className="grid size-7 shrink-0 place-items-center rounded-lg text-muted transition hover:bg-slate-100 hover:text-ink"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-4" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
