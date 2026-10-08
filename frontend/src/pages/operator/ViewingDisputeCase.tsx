import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Escalation } from "../../api/types";
import { ErrorBox } from "../../components/ui";

type Outcome = "VIEWED" | "BUYER_NO_SHOW" | "OWNER_ABSENT";

const OUTCOMES: { value: Outcome; label: string }[] = [
  { value: "VIEWED", label: "Buổi xem đã diễn ra" },
  { value: "BUYER_NO_SHOW", label: "Người mua không đến" },
  { value: "OWNER_ABSENT", label: "Chủ căn không có mặt" },
];

/**
 * The buyer disagrees with the recorded outcome of a viewing. The operator calls both sides (phones shown here),
 * then records what happened; both are told. Past no-shows / absences are shown for reference only.
 */
export function ViewingDisputeCase({ escalation: e }: { escalation: Escalation }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const open = e.status === "OPEN" || e.status === "IN_PROGRESS";
  const record = useMutation({
    mutationFn: (outcome: Outcome) =>
      call(
        api.POST("/api/v1/operator/escalations/{escalation_id}/viewing-outcome", {
          params: { path: { escalation_id: e.id } },
          body: { outcome, note: note.trim() },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["escalations"] }),
  });
  const c = e.context as {
    claim?: string;
    note?: string;
    booking_status?: string;
    buyer_name?: string;
    buyer_phone?: string;
    owner_name?: string;
    owner_phone?: string;
    buyer_no_shows?: number;
    owner_absences?: number;
  };

  return (
    <div className="space-y-3 rounded-xl bg-stone-50 p-3 text-sm">
      <p>
        <span className="font-semibold">Người mua cho biết:</span>{" "}
        {c.claim === "I_CAME" ? "đã đến, nhưng chủ căn ghi là không đến" : "đã đến, nhưng chủ căn không có mặt"}
        {c.note && <span className="text-muted"> — “{c.note}”</span>}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg bg-white p-2.5">
          <p className="font-semibold">Người mua: {c.buyer_name}</p>
          <p className="font-mono">{c.buyer_phone ?? "không có SĐT"}</p>
          <p className="text-xs text-muted">Trước đây bị ghi không đến: {c.buyer_no_shows ?? 0} lần</p>
        </div>
        <div className="rounded-lg bg-white p-2.5">
          <p className="font-semibold">Chủ căn: {c.owner_name}</p>
          <p className="font-mono">{c.owner_phone ?? "không có SĐT"}</p>
          <p className="text-xs text-muted">Trước đây vắng mặt: {c.owner_absences ?? 0} lần</p>
        </div>
      </div>
      {open && (
        <div className="space-y-2 border-t border-stone-200 pt-3">
          <p className="text-xs text-muted">Gọi cho hai bên, rồi ghi lại kết quả. Cả hai được báo.</p>
          {record.isError && <ErrorBox error={record.error} />}
          <input
            className="input"
            placeholder="Đã kiểm tra thế nào? VD: Bảo vệ toà nhà xác nhận khách vào lúc 14h05"
            value={note}
            onChange={(ev) => setNote(ev.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            {OUTCOMES.map((o) => (
              <button
                key={o.value}
                type="button"
                className="btn-secondary btn-sm"
                disabled={record.isPending || note.trim().length < 3}
                onClick={() => record.mutate(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
