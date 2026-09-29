import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, call } from "../api/client";
import { formatDateTime } from "../lib/format";

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
            {list.data?.map((n) => (
              <li key={n.id} className={`border-b border-line px-3 py-2 text-sm last:border-0 ${n.read_at ? "" : "bg-brand-50/60"}`}>
                <p className="font-medium">{n.title}</p>
                {n.body && <p className="text-muted">{n.body}</p>}
                {n.sent_at && <p className="mt-0.5 text-[11px] text-muted">{formatDateTime(n.sent_at)}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
