import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { components } from "../../api/schema";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";

type SellerItem = components["schemas"]["SellerReviewItem"];

/** Owner verification queue (spec §4.15 Operator "Owner verification", AC-04). */
export function SellerVerificationPage() {
  const pending = useQuery({
    queryKey: ["seller-queue"],
    queryFn: () => call(api.GET("/api/v1/operator/sellers", { params: { query: { status: "PENDING" } } })),
  });

  return (
    <div>
      <PageHeader title="Xác thực chủ căn" subtitle="Chỉ chủ căn đã xác thực mới được duyệt tin và nhận lịch xem." />
      {pending.isPending && <Spinner />}
      {pending.isError && <ErrorBox error={pending.error} onRetry={() => pending.refetch()} />}
      {pending.data?.length === 0 && <EmptyState title="Không có hồ sơ nào chờ xác thực" />}
      <ul className="space-y-3">
        {pending.data?.map((s) => (
          <SellerRow key={s.user_id} seller={s} />
        ))}
      </ul>
    </div>
  );
}

function SellerRow({ seller: s }: { seller: SellerItem }) {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const path = { params: { path: { user_id: s.user_id } } };
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: ["seller-queue"] });
  const verify = useMutation({ mutationFn: () => call(api.POST("/api/v1/operator/sellers/{user_id}/verify", path)), onSuccess });
  const reject = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/sellers/{user_id}/reject", { ...path, body: { reason } })),
    onSuccess,
  });
  const busy = verify.isPending || reject.isPending;

  return (
    <li className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium">{s.full_name}</h3>
          <p className="mt-1 text-sm text-muted">
            {s.phone}
            {s.email && ` · ${s.email}`} · Nguồn: {s.source}
          </p>
          {s.id_document_s3_key && <p className="mt-1 font-mono text-xs">Giấy tờ: {s.id_document_s3_key}</p>}
        </div>
        {!rejecting && (
          <div className="flex gap-2">
            <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={() => verify.mutate()}>
              Xác thực
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
          <label htmlFor={`sreason-${s.user_id}`} className="sr-only">
            Lý do
          </label>
          <input
            id={`sreason-${s.user_id}`}
            className="input min-w-0 flex-1"
            required
            minLength={3}
            autoFocus
            placeholder="Lý do (chủ căn sẽ thấy), VD: Ảnh CCCD bị mờ"
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
      {(verify.error ?? reject.error) && <ErrorBox error={verify.error ?? reject.error} />}
    </li>
  );
}
