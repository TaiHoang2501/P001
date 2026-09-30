import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { api, call } from "../../api/client";
import type { Property } from "../../api/types";
import { EmptyState, ErrorBox, Notice, PageHeader, PropertyBadge, Spinner } from "../../components/ui";
import { bedroomsLabel, formatArea, formatVnd } from "../../lib/format";
import { usableRedBooks, useRedBooks } from "./OwnershipVerifyPage";

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
        subtitle="Mỗi tin đăng gắn với một sổ đỏ đã xác thực và cần Chủ đầu tư duyệt trước khi người mua được AI gợi ý."
        action={
          <Link to="/owner/properties/new" className="btn-primary">
            + Đăng bán căn
          </Link>
        }
      />
      <RedBookBanner />
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

/** Selling needs a verified red book (holder name + code + OTP to the owner's phone on record). */
function RedBookBanner() {
  const books = useRedBooks();
  const profile = useQuery({ queryKey: ["owner-verification"], queryFn: () => call(api.GET("/api/v1/owner/verification")) });
  if (!books.data) return null;
  const usable = usableRedBooks(books.data).length;
  const status = profile.data?.verification_status;

  return (
    <div className="mb-4 space-y-2">
      {/* After the red book, the investor/operator still reviews the seller before listings can go live */}
      {status === "PENDING" && (
        <Notice>Hồ sơ người bán đang chờ Chủ đầu tư duyệt. Tin đăng chỉ được duyệt sau khi hồ sơ của bạn được xác thực.</Notice>
      )}
      {status === "REJECTED" && (
        <Notice tone="warning">
          Chủ đầu tư chưa xác thực hồ sơ của bạn{profile.data?.rejection_reason ? `: ${profile.data.rejection_reason}` : ""}. Xác thực
          một sổ đỏ khác để gửi lại hồ sơ, hoặc liên hệ Chủ đầu tư.
        </Notice>
      )}
      {books.data.length === 0 ? (
        <Notice tone="warning">
          Bạn cần xác thực sổ đỏ (họ tên người đứng tên, mã số sổ và mã OTP gửi tới chủ sở hữu) trước khi đăng bán.{" "}
          <Link to="/owner/verify" className="font-medium underline">
            Xác thực sổ đỏ
          </Link>
        </Notice>
      ) : (
        <Notice tone={usable > 0 ? "success" : "info"}>
          {usable > 0
            ? `Bạn có ${usable} sổ đỏ đã xác thực chưa đăng bán.`
            : "Tất cả sổ đỏ đã xác thực của bạn đều đã có tin đăng."}{" "}
          <Link to="/owner/verify" className="font-medium underline">
            {usable > 0 ? "Xem sổ đỏ" : "Xác thực thêm sổ đỏ"}
          </Link>
        </Notice>
      )}
    </div>
  );
}
