import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { api, call } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { formatDateTime } from "../lib/format";
import { noteGroupOf, noteGroups, notificationTarget } from "../lib/notifications";

/** In-app notifications (spec §4.19): viewing requests, confirmations, reminders, escalations. */
export function NotificationBell() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  // Filter chip: "" = all, else a group key (see lib/notifications)
  const [group, setGroup] = useState("");
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
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
        setGroup("");
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const count = unread.data?.unread ?? 0;
  const role = user?.role;
  const notes = (list.data ?? []).map((n) => ({ ...n, group: role ? noteGroupOf(n, role) : "other" }));
  // Only the groups that have something; each shows how many are unread
  const groups = role
    ? noteGroups(role)
        .map((g) => ({
          ...g,
          total: notes.filter((n) => n.group === g.key).length,
          unread: notes.filter((n) => n.group === g.key && !n.read_at).length,
        }))
        .filter((g) => g.total > 0)
    : [];
  const shown = group ? notes.filter((n) => n.group === group) : notes;
  // The group cards are shown when there is more than one kind of notification and none is opened yet
  const overview = !group && groups.length > 1;

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        className="btn-secondary btn-sm relative whitespace-nowrap"
        aria-expanded={open}
        aria-label={`Thông báo${count ? ` (${count} chưa đọc)` : ""}`}
        onClick={() => {
          setOpen((v) => !v);
          setGroup(""); // always start from the group cards
        }}
      >
        {/* Phones: just the bell, so the header fits */}
        <svg viewBox="0 0 24 24" className="size-4 sm:hidden" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9Z" strokeLinejoin="round" />
          <path d="M10 19a2 2 0 0 0 4 0" strokeLinecap="round" />
        </svg>
        <span className="hidden sm:inline">Thông báo</span>
        {count > 0 && (
          <span className="grid min-w-5 place-items-center rounded-full bg-brand-600 px-1 text-[11px] leading-5 text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="card absolute right-0 z-30 mt-2 w-96 max-w-[calc(100vw-2rem)] overflow-hidden shadow-lg">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-sm font-medium">Thông báo</span>
            {count > 0 && (
              <button type="button" className="text-xs text-brand-700 hover:underline" onClick={() => readAll.mutate()}>
                Đánh dấu đã đọc
              </button>
            )}
          </div>
          {/* More than one kind: a card per group first; opening one lists its notifications, with a way back */}
          {overview ? (
            <ul className="max-h-[28rem] space-y-2 overflow-y-auto p-3" aria-label="Nhóm thông báo">
              {groups.map((g) => {
                const latest = notes.find((n) => n.group === g.key);
                return (
                  <li key={g.key}>
                    <button
                      type="button"
                      onClick={() => setGroup(g.key)}
                      className={`w-full rounded-xl border px-3 py-2.5 text-left transition hover:border-brand-500 hover:shadow-sm ${
                        g.unread > 0 ? "border-brand-200 bg-brand-50/60" : "border-line bg-white"
                      }`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold">{g.label}</span>
                        <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted">
                          {g.unread > 0 ? (
                            <span className="grid min-w-5 place-items-center rounded-full bg-brand-600 px-1.5 text-[11px] leading-5 text-white">
                              {g.unread}
                            </span>
                          ) : (
                            `${g.total} thông báo`
                          )}
                          <span aria-hidden="true">›</span>
                        </span>
                      </span>
                      {latest && (
                        <span className="mt-0.5 block truncate text-xs text-muted">
                          {/* The operator's titles only repeat the kind of case: show what the case is about */}
                          {role === "INVESTOR_OPERATOR" && latest.body ? latest.body : latest.title}
                          {latest.sent_at && ` · ${formatDateTime(latest.sent_at)}`}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <>
              {group && (
                <div className="flex items-center gap-2 border-b border-line px-3 py-2">
                  <button
                    type="button"
                    className="rounded-full px-2 py-0.5 text-sm font-semibold text-brand-700 hover:bg-brand-50"
                    onClick={() => setGroup("")}
                  >
                    ← Quay lại
                  </button>
                  <span className="truncate text-sm font-semibold">{groups.find((g) => g.key === group)?.label}</span>
                </div>
              )}
              <ul className="max-h-96 overflow-y-auto">
                {list.isPending && <li className="p-3 text-sm text-muted">Đang tải...</li>}
                {list.data?.length === 0 && <li className="p-3 text-sm text-muted">Chưa có thông báo.</li>}
                {list.data && list.data.length > 0 && shown.length === 0 && (
                  <li className="p-3 text-sm text-muted">Không có thông báo nào trong nhóm này.</li>
                )}
                {shown.map((n) => {
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
            </>
          )}
        </div>
      )}
    </div>
  );
}
