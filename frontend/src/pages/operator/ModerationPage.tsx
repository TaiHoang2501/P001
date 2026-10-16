import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import type { Property } from "../../api/types";
import { imagesOf, PropertyImage } from "../../buyer/shared";
import { PhotoViewer, PropertyPhotoInfo } from "../../components/PhotoViewer";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../../components/ui";
import { bedroomsLabel, DIRECTION, formatArea, formatDateTime, formatVnd, FURNISHING, LEGAL, VIEW } from "../../lib/format";

// Reasons a listing is usually sent back for (the seller fixes it in "Căn đang yêu cầu duyệt")
const REASONS = [
  "Ảnh không phải căn này",
  "Ảnh mờ hoặc quá ít ảnh",
  "Giá chưa hợp lý",
  "Mô tả sai hoặc thiếu",
  "View / nội thất khai chưa đúng",
];

type Tab = "pending" | "live";

export function ModerationPage() {
  // "Chờ duyệt": listings to review; "Đang bán": live listings, which can be taken down when something is wrong
  const [tab, setTab] = useState<Tab>("pending");
  const pending = useQuery({
    queryKey: tab === "pending" ? ["moderation"] : ["moderation", "live"],
    queryFn: () =>
      call(
        api.GET("/api/v1/operator/properties", {
          params: { query: { status: tab === "pending" ? "PENDING_REVIEW" : "AVAILABLE" } },
        }),
      ),
  });

  return (
    <div>
      <PageHeader
        title="Duyệt tin đăng"
        subtitle="Chủ căn đã xác thực sổ đỏ / sổ hồng; kiểm tra ảnh, giá và mô tả. Chỉ tin được duyệt mới được AI gợi ý cho người mua."
      />
      <div className="mb-4 flex gap-1" role="tablist">
        {(
          [
            ["pending", "Chờ duyệt"],
            ["live", "Đang bán"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === key ? "bg-brand-50 text-brand-700" : "text-muted hover:text-ink"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {pending.isPending && <Spinner />}
      {pending.isError && <ErrorBox error={pending.error} onRetry={() => pending.refetch()} />}
      {pending.data?.length === 0 && (
        <EmptyState title={tab === "pending" ? "Không có tin nào chờ duyệt" : "Không có tin nào đang bán"} />
      )}
      <ul className="space-y-3">
        {pending.data?.map((p) => (
          <ModerationRow key={p.id} property={p} live={tab === "live"} />
        ))}
      </ul>
    </div>
  );
}

function ModerationRow({ property: p, live = false }: { property: Property; live?: boolean }) {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const path = { params: { path: { property_id: p.id } } };
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: ["moderation"] });
  // A live listing is taken down (back to the seller with the reason), a pending one rejected
  const endpoint = live
    ? ("/api/v1/operator/properties/{property_id}/take-down" as const)
    : ("/api/v1/operator/properties/{property_id}/reject" as const);

  const approve = useMutation({ mutationFn: () => call(api.POST("/api/v1/operator/properties/{property_id}/approve", path)), onSuccess });
  const reject = useMutation({
    mutationFn: () => call(api.POST(endpoint, { ...path, body: { reason } })),
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
            <span className="font-semibold">{formatVnd(p.price_vnd)}</span>
            {/* Price per m², to spot an odd price at a glance */}
            {Number(p.area_m2) > 0 && (
              <span className="text-muted">
                {" "}
                (≈ {(p.price_vnd / Number(p.area_m2) / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} triệu/m²)
              </span>
            )}{" "}
            · {formatArea(p.area_m2)} · {bedroomsLabel(p.bedrooms)} · Tầng{" "}
            {p.floor} · {DIRECTION[p.direction]} · View {VIEW[p.view]} · {FURNISHING[p.furnishing]} · {LEGAL[p.legal_status]}
          </p>
          {p.description && <p className="mt-2 text-sm text-muted">{p.description}</p>}
          <p className="mt-1 text-xs text-muted">
            Chủ căn {p.owner_name ?? `#${p.owner_id}`}
            {p.owner_phone && (
              <>
                {" "}
                (
                <a href={`tel:${p.owner_phone}`} className="underline-offset-2 hover:underline">
                  {p.owner_phone}
                </a>
                )
              </>
            )}{" "}
            · {live ? "cập nhật lúc" : "gửi duyệt lúc"} {formatDateTime(p.updated_at ?? p.created_at)}
          </p>
          <Evidence property={p} />
        </div>
        {!rejecting && (
          <div className="flex gap-2">
            {!live && (
              <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={() => approve.mutate()}>
                Duyệt
              </button>
            )}
            <button type="button" className="btn-danger btn-sm" disabled={busy} onClick={() => setRejecting(true)}>
              {live ? "Gỡ tin" : "Từ chối"}
            </button>
          </div>
        )}
      </div>
      {rejecting && (
        <form
          className="space-y-2 rounded-xl bg-red-50/60 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            reject.mutate();
          }}
        >
          <label htmlFor={`reason-${p.id}`} className="block text-sm font-semibold">
            {live ? "Lý do gỡ tin" : "Lý do từ chối"}{" "}
            <span className="font-normal text-muted">
              · chủ căn thấy ngay trên tin và sửa theo{live ? "; lịch xem sắp tới sẽ bị hủy và người mua được báo" : ""}
            </span>
          </label>
          {/* Common reasons, one click each; several can be combined, details added below */}
          <div className="flex flex-wrap gap-1.5">
            {REASONS.map((r) => {
              const picked = reason.includes(r);
              return (
                <button
                  key={r}
                  type="button"
                  aria-pressed={picked}
                  onClick={() =>
                    setReason((cur) =>
                      picked
                        ? cur.split("; ").filter((x) => x !== r).join("; ")
                        : [cur.trim(), r].filter(Boolean).join("; "),
                    )
                  }
                  className={`rounded-full border px-3 py-1 text-xs font-semibold ${picked ? "border-red-600 bg-red-600 text-white" : "border-line bg-white hover:border-red-400"}`}
                >
                  {r}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-2">
            <textarea
              id={`reason-${p.id}`}
              className="input min-w-0 flex-1"
              rows={2}
              required
              minLength={10}
              autoFocus
              placeholder="Ghi rõ cần sửa gì, VD: Ảnh phòng khách không phải căn này; giá cao hơn căn cùng tầng khoảng 300 triệu"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <div className="flex flex-col gap-2">
              <button type="submit" className="btn-danger btn-sm" disabled={busy || reason.trim().length < 10}>
                {live ? "Gỡ tin" : "Gửi từ chối"}
              </button>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setRejecting(false)}>
                Thôi
              </button>
            </div>
          </div>
        </form>
      )}
      {(approve.error ?? reject.error) && <ErrorBox error={approve.error ?? reject.error} />}
    </li>
  );
}

/** What the investor checks: the photos (one viewer with previous / next) against the home's facts. */
function Evidence({ property: p }: { property: Property }) {
  const [viewer, setViewer] = useState<number | null>(null);
  const photos = imagesOf(p);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3">
      {photos.length > 0 ? (
        <button
          type="button"
          onClick={() => setViewer(0)}
          className="group flex items-center gap-3 rounded-2xl border border-line bg-white p-1.5 pr-4 text-left text-sm hover:border-brand-500"
          aria-label={`Xem ${photos.length} ảnh căn ${p.unit_code}`}
        >
          <PropertyImage src={photos[0].url} alt="" className="h-14 w-20 rounded-xl" />
          <span>
            <span className="block font-semibold">Xem {photos.length} ảnh</span>
            <span className="block text-xs text-muted">Bấm để xem lần lượt</span>
          </span>
        </button>
      ) : (
        <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">Chưa có ảnh</span>
      )}
      {/* Ownership was proven by the seller (red book + OTP); the home's facts above come from that red book */}
      {p.verified_red_book && (
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
          ✓ Sổ đỏ / sổ hồng {p.red_book_code ?? ""} đã xác thực · thông tin căn theo dữ liệu Chủ đầu tư
        </span>
      )}
      {viewer !== null && (
        <PhotoViewer
          images={photos}
          start={viewer}
          title={p.unit_code}
          info={<PropertyPhotoInfo property={p} />}
          onClose={() => setViewer(null)}
        />
      )}
    </div>
  );
}
