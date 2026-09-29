import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, call } from "../../api/client";
import type { Property } from "../../api/types";
import { EmptyState, ErrorBox, Notice, PageHeader, PropertyBadge, Spinner } from "../../components/ui";
import { bedroomsLabel, formatArea, formatVnd } from "../../lib/format";

const EDITABLE = new Set<Property["status"]>(["DRAFT", "REJECTED", "WITHDRAWN"]);

export function OwnerPropertiesPage() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["owner-properties"], queryFn: () => call(api.GET("/api/v1/owner/properties")) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["owner-properties"] });
  const path = (id: number) => ({ params: { path: { property_id: id } } });

  const submit = useMutation({
    mutationFn: (id: number) => call(api.POST("/api/v1/owner/properties/{property_id}/submit", path(id))),
    onSuccess: refresh,
  });
  const withdraw = useMutation({
    mutationFn: (id: number) => call(api.POST("/api/v1/owner/properties/{property_id}/withdraw", path(id))),
    onSuccess: refresh,
  });
  const sold = useMutation({
    mutationFn: (id: number) => call(api.POST("/api/v1/owner/properties/{property_id}/sold", path(id))),
    onSuccess: refresh,
  });
  const actionError = submit.error ?? withdraw.error ?? sold.error;

  return (
    <div>
      <PageHeader
        title="Căn của tôi"
        subtitle="Tin mới cần Chủ đầu tư duyệt (kèm giấy tờ sở hữu) trước khi người mua được AI gợi ý."
        action={
          <Link to="/owner/properties/new" className="btn-primary">
            + Đăng bán căn
          </Link>
        }
      />
      <VerificationBanner />
      {actionError && (
        <div className="mb-4">
          <ErrorBox error={actionError} />
        </div>
      )}
      {list.isPending && <Spinner />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => list.refetch()} />}
      {list.data?.length === 0 && <EmptyState title="Bạn chưa đăng căn nào">Bấm “Đăng bán căn” để bắt đầu.</EmptyState>}

      <ul className="space-y-3">
        {list.data?.map((p) => (
          <li key={p.id} className="card p-4">
            <div className="flex flex-wrap items-start gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-medium">
                    {p.project_name} · {p.building_name} · {p.unit_code}
                  </h3>
                  <PropertyBadge status={p.status} />
                </div>
                <p className="mt-1 text-sm text-muted">
                  {formatVnd(p.price_vnd)} · {formatArea(p.area_m2)} · {bedroomsLabel(p.bedrooms)} · Tầng {p.floor} ·{" "}
                  {(p.media ?? []).length} ảnh/giấy tờ
                </p>
                {p.status === "REJECTED" && p.rejection_reason && (
                  <p className="mt-2 text-sm text-red-700">Lý do từ chối: {p.rejection_reason}</p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {EDITABLE.has(p.status) && (
                  <>
                    <Link to={`/owner/properties/${p.id}/edit`} className="btn-secondary btn-sm">
                      Sửa & giấy tờ
                    </Link>
                    <button type="button" className="btn-primary btn-sm" disabled={submit.isPending} onClick={() => submit.mutate(p.id)}>
                      Gửi duyệt
                    </button>
                  </>
                )}
                {p.status !== "SOLD" && (
                  <Link to={`/owner/properties/${p.id}/slots`} className="btn-secondary btn-sm">
                    Lịch trống
                  </Link>
                )}
                {p.status === "AVAILABLE" && (
                  <>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      disabled={withdraw.isPending}
                      onClick={() => {
                        if (window.confirm("Tạm ngừng bán căn này? Căn sẽ không còn được gợi ý cho người mua.")) withdraw.mutate(p.id);
                      }}
                    >
                      Tạm ngừng
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      disabled={sold.isPending}
                      onClick={() => {
                        if (window.confirm("Đánh dấu căn này đã bán?")) sold.mutate(p.id);
                      }}
                    >
                      Đã bán
                    </button>
                  </>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Owner verification (spec §4.5 "Owner Verification", AC-04): required before listings go live. */
function VerificationBanner() {
  const queryClient = useQueryClient();
  const [docKey, setDocKey] = useState("");
  const profile = useQuery({ queryKey: ["owner-verification"], queryFn: () => call(api.GET("/api/v1/owner/verification")) });
  const submit = useMutation({
    mutationFn: () => call(api.POST("/api/v1/owner/verification", { body: { id_document_s3_key: docKey.trim() } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["owner-verification"] }),
  });

  if (!profile.data) return null;
  const status = profile.data.verification_status;
  if (status === "VERIFIED") return null;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit.mutate();
  }

  return (
    <div className="mb-4 space-y-2">
      {status === "PENDING" ? (
        <Notice>Hồ sơ chủ căn đang chờ Chủ đầu tư xác thực. Tin đăng chỉ được duyệt sau khi bạn được xác thực.</Notice>
      ) : (
        <Notice tone="warning">
          {status === "REJECTED"
            ? `Xác thực chưa thành công: ${profile.data.rejection_reason ?? ""}. Vui lòng gửi lại giấy tờ.`
            : "Bạn cần xác thực chủ căn (CCCD) trước khi tin đăng được duyệt và người mua đặt lịch xem."}
          <form onSubmit={onSubmit} className="mt-2 flex flex-wrap gap-2">
            <label htmlFor="id-doc" className="sr-only">
              Ảnh CCCD (S3 key hoặc URL)
            </label>
            <input
              id="id-doc"
              className="input min-w-0 flex-1 font-mono text-xs"
              required
              minLength={3}
              placeholder="S3 key/URL ảnh CCCD"
              value={docKey}
              onChange={(e) => setDocKey(e.target.value)}
            />
            <button type="submit" className="btn-primary btn-sm" disabled={submit.isPending}>
              Gửi xác thực
            </button>
          </form>
        </Notice>
      )}
      {submit.isError && <ErrorBox error={submit.error} />}
    </div>
  );
}
