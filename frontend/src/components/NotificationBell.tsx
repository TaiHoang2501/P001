import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { api, call } from "../api/client";
import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { formatDateTime } from "../lib/format";

type Note = { event_type: string; booking_id?: number | null; payload?: Record<string, unknown> | null };

/** Where a notification leads: the booking, listing or queue it is about, in the reader's own area. */
export function notificationTarget(n: Note, role: Role): string | null {
  const payload = (n.payload ?? {}) as { property_id?: number };
  const booking = n.booking_id;
  switch (role) {
    case "OWNER":
      if (booking) return `/owner/bookings?booking=${booking}`;
      if (n.event_type.startsWith("LISTING_")) return payload.property_id ? `/owner?property=${payload.property_id}` : "/owner";
      if (n.event_type.startsWith("SELLER_")) return "/owner/verify";
      return null;
    case "CUSTOMER":
      if (booking) return `/buyer/chat?booking=${booking}`;
      if (payload.property_id) return `/buyer/chat?property=${payload.property_id}`;
      return "/buyer/chat";
    case "INVESTOR_OPERATOR":
      if (n.event_type.startsWith("ESCALATION_")) return "/operator/escalations";
      if (booking) return "/operator/bookings";
      return null;
    default:
      return null;
  }
}

/** In-app notifications (spec §4.19): viewing requests, confirmations, reminders, escalations. */
export function NotificationBell() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => call(api.GET("/api/v1/notifications/unread-count")),
    refetchInterval: 30_000,
  });
  const list = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => call(api.GET("/api/v1/notifications")),
    enabled: open,
  });
  const { user } = useAuth();
  const navigate = useNavigate();
  const readOne = useMutation({
    mutationFn: (id: number) =>
      call(api.POST("/api/v1/notifications/{notification_id}/read", { params: { path: { notification_id: id } } })),
    // The unread count goes down right away
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const readAll = useMutation({
    mutationFn: () => call(api.POST("/api/v1/notifications/read-all")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const count = unread.data?.unread ?? 0;

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        className="btn-secondary btn-sm relative"
        aria-expanded={open}
        aria-label={`Thông báo${count ? ` (${count} chưa đọc)` : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        Thông báo
        {count > 0 && (
          <span className="grid min-w-5 place-items-center rounded-full bg-brand-600 px-1 text-[11px] leading-5 text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="card absolute right-0 z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden shadow-lg">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-sm font-medium">Thông báo</span>
            {count > 0 && (
              <button type="button" className="text-xs text-brand-700 hover:underline" onClick={() => readAll.mutate()}>
                Đánh dấu đã đọc
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {list.isPending && <li className="p-3 text-sm text-muted">Đang tải...</li>}
            {list.data?.length === 0 && <li className="p-3 text-sm text-muted">Chưa có thông báo.</li>}
            {list.data?.map((n) => {
              const target = user ? notificationTarget(n, user.role) : null;
              const unread = !n.read_at;
              return (
                <li key={n.id} className="border-b border-line last:border-0">
                  <button
                    type="button"
                    className={`flex w-full gap-2.5 px-3 py-2 text-left text-sm hover:bg-slate-50 ${unread ? "bg-brand-50/60" : ""}`}
                    onClick={() => {
                      if (unread) readOne.mutate(n.id);
                      setOpen(false);
                      if (target) navigate(target);
                    }}
                  >
                    {/* Blue dot = not read yet */}
                    <span
                      className={`mt-1.5 size-2 shrink-0 rounded-full ${unread ? "bg-blue-600" : "bg-transparent"}`}
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1">
                      <span className={`block ${unread ? "font-semibold" : "font-medium"}`}>
                        {n.title}
                        {unread && <span className="sr-only"> (chưa đọc)</span>}
                      </span>
                      {n.body && <span className="block text-muted">{n.body}</span>}
                      {n.sent_at && <span className="mt-0.5 block text-[11px] text-muted">{formatDateTime(n.sent_at)}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
