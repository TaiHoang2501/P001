import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Escalation } from "../../api/types";
import { BOOKING_STATUS, formatDateTime } from "../../lib/format";

// Messages shown before "Xem cả đoạn chat"
const FIRST_SHOWN = 4;

/**
 * A case in plain words: who is involved (names and phones, for calling them), which home and viewing, and for a
 * case the assistant raised, the end of the buyer's chat with it — as the buyer saw it, nothing technical.
 */
export function CaseContext({ escalation: e }: { escalation: Escalation }) {
  const [all, setAll] = useState(false);
  const ctx = useQuery({
    queryKey: ["escalation-context", e.id],
    queryFn: () =>
      call(api.GET("/api/v1/operator/escalations/{escalation_id}/context", { params: { path: { escalation_id: e.id } } })),
  });
  const c = ctx.data;
  if (!c) return null;

  const people: { label: string; name: string; phone?: string | null }[] = [];
  if (c.buyer_name) people.push({ label: "Người mua", name: c.buyer_name, phone: c.buyer_phone });
  if (c.seller_name) people.push({ label: "Chủ căn", name: c.seller_name, phone: c.seller_phone });
  const messages = c.messages ?? [];
  const shown = all ? messages : messages.slice(-FIRST_SHOWN);
  const hidden = messages.length - shown.length + (c.earlier_messages ?? 0);

  return (
    <div className="space-y-3">
      {(people.length > 0 || c.property_label) && (
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          {people.map((p) => (
            <div key={p.label} className="rounded-lg bg-stone-50 px-3 py-2">
              <p className="text-xs text-muted">{p.label}</p>
              <p className="font-semibold">{p.name}</p>
              {p.phone && (
                <a href={`tel:${p.phone}`} className="font-mono text-brand-700 hover:underline">
                  {p.phone}
                </a>
              )}
            </div>
          ))}
          {c.property_label && (
            <div className="rounded-lg bg-stone-50 px-3 py-2 sm:col-span-2">
              <p className="text-xs text-muted">Căn</p>
              <p className="font-semibold">{c.property_label}</p>
              {c.viewing_time && (
                <p className="text-muted">
                  Lịch xem {formatDateTime(c.viewing_time)}
                  {c.viewing_status && ` · ${BOOKING_STATUS[c.viewing_status as keyof typeof BOOKING_STATUS] ?? c.viewing_status}`}
                  {c.deal_code && ` · ${c.deal_code}`}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {messages.length > 0 && (
        <section className="rounded-lg border border-line p-3" aria-label="Đoạn chat với Trợ lý AI">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Đoạn chat với Trợ lý AI</p>
          {hidden > 0 && !all && (
            <button type="button" className="mb-2 text-xs font-semibold text-brand-700 hover:underline" onClick={() => setAll(true)}>
              Xem cả đoạn chat ({hidden} tin trước đó)
            </button>
          )}
          <ol className="space-y-2">
            {shown.map((m, i) => (
              <li key={i} className={`flex ${m.role === "USER" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                    m.role === "USER" ? "bg-brand-600 text-white" : "bg-stone-100 text-ink"
                  }`}
                >
                  <p className="whitespace-pre-line">{m.content.replace(/\*\*/g, "")}</p>
                  <p className={`mt-0.5 text-[11px] ${m.role === "USER" ? "text-white/70" : "text-muted"}`}>
                    {m.role === "USER" ? "Khách" : "Trợ lý"} · {formatDateTime(m.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
