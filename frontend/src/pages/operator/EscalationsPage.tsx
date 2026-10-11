import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import type { Escalation } from "../../api/types";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { useJumpFlash } from "../../lib/jump";
import { CaseContext } from "./CaseContext";
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
  OWNERSHIP_SUPPORT: "Hỗ trợ xác thực sổ đỏ / sổ hồng",
  VIEWING_DISPUTE: "Tranh chấp kết quả buổi xem",
};

const STATUS: Record<Escalation["status"], { text: string; tone: string }> = {
  OPEN: { text: "Chờ nhận", tone: "bg-amber-100 text-amber-900" },
  IN_PROGRESS: { text: "Đang xử lý", tone: "bg-sky-100 text-sky-900" },
  RESOLVED: { text: "Đã xử lý", tone: "bg-emerald-100 text-emerald-900" },
  DISMISSED: { text: "Đã bỏ qua", tone: "bg-stone-200 text-stone-700" },
};

const RAISED_BY: Record<Escalation["raised_by"], string> = { USER: "Người dùng", AI_AGENT: "Trợ lý AI", SYSTEM: "Hệ thống" };

/** Exception queue (spec §4.15 Operator, §4.3 HITL, §6.4): what the AI or the system could not resolve. */
export function EscalationsPage() {
  const [params] = useSearchParams();
  // Opened from a notification (?case=ID): that case lights up; a closed one is looked for among the handled ones
  const opened = Number(params.get("case")) || null;
  const [showClosed, setShowClosed] = useState(false);
  const queue = useQuery({
    queryKey: ["escalations", showClosed],
    queryFn: () =>
      call(api.GET("/api/v1/operator/escalations", { params: { query: showClosed ? { status: "RESOLVED" } : {} } })),
  });
  const missing = opened !== null && queue.data !== undefined && !queue.data.some((e) => e.id === opened);
  useEffect(() => {
    if (missing && !showClosed) setShowClosed(true);
  }, [missing, showClosed]);

  return (
    <div>
      <PageHeader
        title="Hàng đợi ngoại lệ"
        subtitle="Các trường hợp AI, hệ thống hoặc người dùng chuyển cho nhân viên Chủ đầu tư (kể cả hỗ trợ xác thực sổ đỏ / sổ hồng); người gửi được báo kết quả khi bạn đóng."
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
          <EscalationRow key={e.id} escalation={e} opened={e.id === opened} />
        ))}
      </ul>
    </div>
  );
}

// Same as the server's rule for the outcome note
const MIN_NOTE = 10;

function EscalationRow({ escalation: e, opened = false }: { escalation: Escalation; opened?: boolean }) {
  const flash = useJumpFlash(opened);
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [resolution, setResolution] = useState("");
  // Who hears the outcome: preset for the kind of case, the operator can change it
  const ctx = useQuery({
    queryKey: ["escalation-context", e.id],
    queryFn: () =>
      call(api.GET("/api/v1/operator/escalations/{escalation_id}/context", { params: { path: { escalation_id: e.id } } })),
  });
  const [tellBuyer, setTellBuyer] = useState<boolean | null>(null);
  const [tellSeller, setTellSeller] = useState<boolean | null>(null);
  const buyerTold = tellBuyer ?? ctx.data?.notify_buyer_default ?? false;
  const sellerTold = tellSeller ?? ctx.data?.notify_seller_default ?? false;
  const outcome = { resolution, notify_buyer: buyerTold, notify_seller: sellerTold };
  const path = { params: { path: { escalation_id: e.id } } };
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: ["escalations"] });
  const assign = useMutation({ mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/assign", path)), onSuccess });
  const resolve = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/resolve", { ...path, body: outcome })),
    onSuccess,
  });
  const dismiss = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/dismiss", { ...path, body: outcome })),
    onSuccess,
  });
  const open = e.status === "OPEN" || e.status === "IN_PROGRESS";
  const busy = assign.isPending || resolve.isPending || dismiss.isPending;
  // A colleague has taken this case: it is theirs to close, unless this operator takes it over
  const othersCase = e.status === "IN_PROGRESS" && e.assigned_to !== null && e.assigned_to !== user?.id;
  // The people told read this note: a few meaningful words, the same rule for both buttons
  const noteReady = resolution.trim().length >= MIN_NOTE;
  const canClose = noteReady && !othersCase && !busy;
  const error = assign.error ?? resolve.error ?? dismiss.error;

  return (
    <li ref={flash} className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{TYPE[e.type]}</h3>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS[e.status].tone}`}>
              {STATUS[e.status].text}
            </span>
            {e.status === "IN_PROGRESS" && e.assigned_to && (
              <span className="text-xs text-muted">
                {e.assigned_to === user?.id ? "Bạn đang xử lý" : `${e.assigned_to_name ?? "Đồng nghiệp"} đang xử lý`}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm">{e.summary}</p>
          {/* Who and which home are shown by name below, not as internal ids */}
          <p className="mt-1 text-xs text-muted">
            {RAISED_BY[e.raised_by]} · {formatDateTime(e.created_at)}
          </p>
          {e.resolution && <p className="mt-1 text-sm text-emerald-800">Kết quả: {e.resolution}</p>}
          {!open && e.resolved_at && (
            <p className="mt-1 text-xs text-muted">
              {e.assigned_to_name ? `${e.assigned_to_name} · ` : "Hệ thống tự đóng · "}
              {formatDateTime(e.resolved_at)}
            </p>
          )}
        </div>
        {(e.status === "OPEN" || othersCase) && (
          <button
            type="button"
            className="btn-secondary btn-sm"
            disabled={busy}
            title={
              othersCase
                ? "Chuyển ca sang tên bạn (khi đồng nghiệp vắng hoặc nhờ bạn làm tiếp)"
                : "Ghi tên bạn vào ca, để đồng nghiệp biết ca này đã có người lo"
            }
            onClick={() => {
              if (!othersCase || window.confirm(`${e.assigned_to_name ?? "Đồng nghiệp"} đang xử lý ca này. Bạn nhận lại?`))
                assign.mutate();
            }}
          >
            {othersCase ? "Nhận lại ca" : "Nhận xử lý"}
          </button>
        )}
      </div>
      {/* Red book support and viewing disputes have their own panels with the people involved */}
      {e.type !== "OWNERSHIP_SUPPORT" && e.type !== "VIEWING_DISPUTE" && <CaseContext escalation={e} />}
      {e.type === "OWNERSHIP_SUPPORT" && <OwnershipCase escalation={e} />}
      {e.type === "VIEWING_DISPUTE" && <ViewingDisputeCase escalation={e} />}
      {open && (
        <form
          className="space-y-2 border-t border-line pt-3"
          onSubmit={(ev) => {
            ev.preventDefault();
            resolve.mutate();
          }}
        >
          <label htmlFor={`res-${e.id}`} className="text-sm font-semibold">
            Kết quả xử lý
          </label>
          <input
            id={`res-${e.id}`}
            className="input w-full"
            required
            minLength={MIN_NOTE}
            placeholder={
              e.type === "OWNERSHIP_SUPPORT"
                ? "VD: Giấy ủy quyền chưa công chứng, vui lòng bổ sung"
                : "VD: Đã hẹn chủ căn tiếp khách 19h thứ 6"
            }
            value={resolution}
            onChange={(ev) => setResolution(ev.target.value)}
          />
          {(ctx.data?.buyer_name || ctx.data?.seller_name) && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span className="text-muted">Gửi lời nhắn này tới:</span>
              {ctx.data?.buyer_name && (
                <label className="flex items-center gap-1.5">
                  <input type="checkbox" checked={buyerTold} onChange={(ev) => setTellBuyer(ev.target.checked)} />
                  Người mua {ctx.data.buyer_name}
                </label>
              )}
              {ctx.data?.seller_name && (
                <label className="flex items-center gap-1.5">
                  <input type="checkbox" checked={sellerTold} onChange={(ev) => setTellSeller(ev.target.checked)} />
                  Chủ căn {ctx.data.seller_name}
                </label>
              )}
            </div>
          )}
          {othersCase ? (
            <p className="text-xs text-amber-800">
              {e.assigned_to_name ?? "Đồng nghiệp"} đang xử lý ca này; bấm “Nhận lại ca” nếu bạn làm tiếp.
            </p>
          ) : (
            !noteReady && <p className="text-xs text-muted">Ghi ít nhất {MIN_NOTE} ký tự: đây là lời nhắn người được báo sẽ đọc.</p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <button type="submit" className="btn-primary btn-sm" disabled={!canClose}>
              Đã xử lý
            </button>
            <span className="text-xs text-muted">đã giải quyết xong</span>
            <button
              type="button"
              className="btn-secondary btn-sm ml-2"
              disabled={!canClose}
              onClick={() => dismiss.mutate()}
            >
              Bỏ qua
            </button>
            <span className="text-xs text-muted">không cần xử lý (VD ca trùng, thiếu giấy tờ)</span>
          </div>
        </form>
      )}
      {error && <ErrorBox error={error} />}
    </li>
  );
}
