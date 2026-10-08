import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Escalation } from "../../api/types";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { OwnershipCase } from "./OwnershipCase";
import { ViewingDisputeCase } from "./ViewingDisputeCase";

const TYPE: Record<Escalation["type"], string> = {
  SELLER_NO_RESPONSE: "Chủ căn chưa phản hồi",
  NO_COMMON_SLOT: "Không có giờ xem chung",
  SCHEDULE_CONFLICT: "Xung đột lịch",
  PROPERTY_ISSUE: "Vấn đề về căn",
  MULTI_BUYER: "Nhiều người mua cùng căn",
  SYSTEM_FAILURE: "Lỗi hệ thống",
  OTHER: "Khác",
  OWNERSHIP_SUPPORT: "Hỗ trợ xác thực sổ đỏ",
  VIEWING_DISPUTE: "Tranh chấp kết quả buổi xem",
};

const RAISED_BY: Record<Escalation["raised_by"], string> = { USER: "Người dùng", AI_AGENT: "Trợ lý AI", SYSTEM: "Hệ thống" };

/** Exception queue (spec §4.15 Operator, §4.3 HITL, §6.4): what the AI or the system could not resolve. */
export function EscalationsPage() {
  const [showClosed, setShowClosed] = useState(false);
  const queue = useQuery({
    queryKey: ["escalations", showClosed],
    queryFn: () =>
      call(api.GET("/api/v1/operator/escalations", { params: { query: showClosed ? { status: "RESOLVED" } : {} } })),
  });

  return (
    <div>
      <PageHeader
        title="Hàng đợi ngoại lệ"
        subtitle="Các trường hợp AI, hệ thống hoặc người dùng chuyển cho người xử lý (kể cả hỗ trợ xác thực sổ đỏ); người gửi được báo kết quả khi bạn đóng."
        action={
          <button type="button" className="btn-secondary btn-sm" onClick={() => setShowClosed((v) => !v)}>
            {showClosed ? "Xem đang mở" : "Xem đã xử lý"}
          </button>
        }
      />
      {queue.isPending && <Spinner />}
      {queue.isError && <ErrorBox error={queue.error} onRetry={() => queue.refetch()} />}
      {queue.data?.length === 0 && <EmptyState title={showClosed ? "Chưa có trường hợp đã xử lý" : "Không có trường hợp nào đang chờ"} />}
      <ul className="space-y-3">
        {queue.data?.map((e) => (
          <EscalationRow key={e.id} escalation={e} />
        ))}
      </ul>
    </div>
  );
}

function EscalationRow({ escalation: e }: { escalation: Escalation }) {
  const queryClient = useQueryClient();
  const [resolution, setResolution] = useState("");
  const path = { params: { path: { escalation_id: e.id } } };
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: ["escalations"] });
  const assign = useMutation({ mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/assign", path)), onSuccess });
  const resolve = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/resolve", { ...path, body: { resolution } })),
    onSuccess,
  });
  const dismiss = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/dismiss", { ...path, body: { resolution } })),
    onSuccess,
  });
  const open = e.status === "OPEN" || e.status === "IN_PROGRESS";
  const busy = assign.isPending || resolve.isPending || dismiss.isPending;
  const error = assign.error ?? resolve.error ?? dismiss.error;

  return (
    <li className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{TYPE[e.type]}</h3>
            <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-700">{e.status}</span>
          </div>
          <p className="mt-1 text-sm">{e.summary}</p>
          <p className="mt-1 text-xs text-muted">
            {RAISED_BY[e.raised_by]} · {formatDateTime(e.created_at)}
            {e.requester_id && ` · Người dùng #${e.requester_id}`}
            {e.booking_id && ` · Booking #${e.booking_id}`}
            {e.property_id && ` · Căn #${e.property_id}`}
          </p>
          {e.resolution && <p className="mt-1 text-sm text-emerald-800">Kết quả: {e.resolution}</p>}
        </div>
        {e.status === "OPEN" && (
          <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={() => assign.mutate()}>
            Nhận xử lý
          </button>
        )}
      </div>
      {e.type === "OWNERSHIP_SUPPORT" && <OwnershipCase escalation={e} />}
      {e.type === "VIEWING_DISPUTE" && <ViewingDisputeCase escalation={e} />}
      {open && (
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            resolve.mutate();
          }}
        >
          <label htmlFor={`res-${e.id}`} className="sr-only">
            Kết quả xử lý
          </label>
          <input
            id={`res-${e.id}`}
            className="input min-w-0 flex-1"
            required
            minLength={3}
            placeholder={
              e.type === "OWNERSHIP_SUPPORT"
                ? "Hoặc đóng ca với lời nhắn (người bán sẽ thấy), VD: Giấy ủy quyền chưa công chứng, vui lòng bổ sung"
                : "Kết quả (người mua sẽ thấy), VD: Đã hẹn chủ căn 19h thứ 6"
            }
            value={resolution}
            onChange={(ev) => setResolution(ev.target.value)}
          />
          <button type="submit" className="btn-primary btn-sm" disabled={busy}>
            Đã xử lý
          </button>
          <button type="button" className="btn-secondary btn-sm" disabled={busy || resolution.trim().length < 3} onClick={() => dismiss.mutate()}>
            Bỏ qua
          </button>
        </form>
      )}
      {error && <ErrorBox error={error} />}
    </li>
  );
}
