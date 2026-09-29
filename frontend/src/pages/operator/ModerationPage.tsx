import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Property } from "../../api/types";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { bedroomsLabel, DIRECTION, formatArea, formatDateTime, formatVnd, FURNISHING, LEGAL, VIEW } from "../../lib/format";

export function ModerationPage() {
  const pending = useQuery({
    queryKey: ["moderation"],
    queryFn: () => call(api.GET("/api/v1/operator/properties", { params: { query: { status: "PENDING_REVIEW" } } })),
  });

  return (
    <div>
      <PageHeader title="Duyệt tin đăng" subtitle="Kiểm tra giấy tờ sở hữu; chỉ tin được duyệt mới được AI gợi ý cho người mua." />
      {pending.isPending && <Spinner />}
      {pending.isError && <ErrorBox error={pending.error} onRetry={() => pending.refetch()} />}
      {pending.data?.length === 0 && <EmptyState title="Không có tin nào chờ duyệt" />}
      <ul className="space-y-3">
        {pending.data?.map((p) => (
          <ModerationRow key={p.id} property={p} />
        ))}
      </ul>
    </div>
  );
}

function ModerationRow({ property: p }: { property: Property }) {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const path = { params: { path: { property_id: p.id } } };
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: ["moderation"] });

  const approve = useMutation({ mutationFn: () => call(api.POST("/api/v1/operator/properties/{property_id}/approve", path)), onSuccess });
  const reject = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/properties/{property_id}/reject", { ...path, body: { reason } })),
    onSuccess,
  });
  const busy = approve.isPending || reject.isPending;

  return (
    <li className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium">
            {p.project_name} · {p.building_name} · {p.unit_code}
          </h3>
          <p className="mt-1 text-sm">
            <span className="font-semibold">{formatVnd(p.price_vnd)}</span> · {formatArea(p.area_m2)} · {bedroomsLabel(p.bedrooms)} · Tầng{" "}
            {p.floor} · {DIRECTION[p.direction]} · View {VIEW[p.view]} · {FURNISHING[p.furnishing]} · {LEGAL[p.legal_status]}
          </p>
          {p.description && <p className="mt-2 text-sm text-muted">{p.description}</p>}
          <p className="mt-1 text-xs text-muted">
            Chủ căn #{p.owner_id} · tạo lúc {formatDateTime(p.created_at)}
          </p>
          {(p.media ?? []).length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
              {(p.media ?? []).map((m) => (
                <li key={m.id}>
                  <a
                    href={m.url}
                    target="_blank"
                    rel="noreferrer"
                    className={`rounded-full px-2 py-0.5 hover:underline ${m.kind === "OWNERSHIP_DOC" ? "bg-amber-100 text-amber-900" : "bg-stone-100 text-stone-700"}`}
                  >
                    {m.kind === "OWNERSHIP_DOC" ? "Giấy tờ sở hữu" : m.kind === "IMAGE" ? "Ảnh" : m.kind}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
        {!rejecting && (
          <div className="flex gap-2">
            <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={() => approve.mutate()}>
              Duyệt
            </button>
            <button type="button" className="btn-danger btn-sm" disabled={busy} onClick={() => setRejecting(true)}>
              Từ chối
            </button>
          </div>
        )}
      </div>
      {rejecting && (
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            reject.mutate();
          }}
        >
          <label htmlFor={`reason-${p.id}`} className="sr-only">
            Lý do từ chối
          </label>
          <input
            id={`reason-${p.id}`}
            className="input min-w-0 flex-1"
            required
            minLength={3}
            autoFocus
            placeholder="Lý do (chủ căn sẽ thấy), VD: Giấy tờ không khớp mã căn"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button type="submit" className="btn-danger btn-sm" disabled={busy}>
            Gửi từ chối
          </button>
          <button type="button" className="btn-secondary btn-sm" onClick={() => setRejecting(false)}>
            Thôi
          </button>
        </form>
      )}
      {(approve.error ?? reject.error) && <ErrorBox error={approve.error ?? reject.error} />}
    </li>
  );
}
