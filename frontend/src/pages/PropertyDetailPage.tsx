import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router";

import { api, ApiError, call } from "../api/client";
import type { Booking, TimeWindow } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, Notice, Spinner } from "../components/ui";
import { ViewingTimePicker } from "../components/ViewingTimePicker";
import {
  bedroomsLabel,
  DIRECTION,
  formatArea,
  formatVnd,
  FURNISHING,
  LEGAL,
  PROPERTY_TYPE,
  VIEW,
} from "../lib/format";

export function PropertyDetailPage() {
  const id = Number(useParams().id);
  const property = useQuery({
    queryKey: ["property", id],
    queryFn: () => call(api.GET("/api/v1/properties/{property_id}", { params: { path: { property_id: id } } })),
  });

  if (property.isPending) return <Spinner />;
  if (property.isError) return <ErrorBox error={property.error} onRetry={() => property.refetch()} />;
  const p = property.data;
  const images = (p.media ?? []).filter((m) => m.kind === "IMAGE" || m.kind === "FLOORPLAN").map((m) => m.url);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div className="space-y-6">
        <div>
          <Link to="/" className="text-sm text-muted hover:text-ink">
            ← Quay lại trợ lý AI
          </Link>
          <p className="mt-3 text-sm font-medium uppercase tracking-wide text-brand-700">{p.project_name}</p>
          <h1 className="page-title">
            {p.building_name} · Căn {p.unit_code}
          </h1>
          <p className="mt-2 text-3xl font-semibold">{formatVnd(p.price_vnd)}</p>
        </div>

        {images.length > 0 ? (
          <div className="grid grid-cols-2 gap-2">
            {images.map((src) => (
              <img key={src} src={src} alt={`Ảnh căn ${p.unit_code}`} className="aspect-video w-full rounded-lg object-cover" />
            ))}
          </div>
        ) : (
          <div className="grid aspect-[16/7] place-items-center rounded-xl border border-dashed border-line bg-white text-sm text-muted">
            Chủ căn chưa tải ảnh
          </div>
        )}

        <section className="card p-5">
          <h2 className="mb-3 font-semibold">Thông tin căn</h2>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <Row label="Loại hình" value={PROPERTY_TYPE[p.property_type]} />
            <Row label="Diện tích" value={formatArea(p.area_m2)} />
            <Row label="Phòng ngủ" value={bedroomsLabel(p.bedrooms)} />
            <Row label="Phòng tắm" value={String(p.bathrooms)} />
            <Row label="Tầng" value={String(p.floor)} />
            <Row label="Hướng" value={DIRECTION[p.direction]} />
            <Row label="View" value={VIEW[p.view]} />
            <Row label="Nội thất" value={FURNISHING[p.furnishing]} />
            <Row label="Pháp lý" value={LEGAL[p.legal_status]} />
            <Row label="Khu vực" value={p.city} />
          </dl>
          {p.description && <p className="mt-4 whitespace-pre-line text-sm leading-relaxed">{p.description}</p>}
        </section>
      </div>

      <BookingPanel propertyId={p.id} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line py-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

function BookingPanel({ propertyId }: { propertyId: number }) {
  const { user } = useAuth();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [created, setCreated] = useState<Booking | null>(null);

  const book = useMutation({
    mutationFn: ({ startAt, windows }: { startAt: string; windows: TimeWindow[] }) =>
      call(
        api.POST("/api/v1/bookings", {
          body: { property_id: propertyId, start_at: startAt, buyer_windows: windows, note: note.trim() || null },
        }),
      ),
    onSuccess: (booking) => {
      setCreated(booking);
      setNote("");
      queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
    },
  });

  return (
    <aside className="card h-fit space-y-4 p-5 lg:sticky lg:top-20" aria-labelledby="book-title">
      <h2 id="book-title" className="font-semibold">
        Đặt lịch xem nhà
      </h2>

      {created && (
        <Notice tone="success">
          Đã gửi yêu cầu xem tới chủ căn — mã deal <strong>{created.deal_code}</strong>. Lịch <strong>chưa được xác nhận</strong> cho đến
          khi chủ căn đồng ý; theo dõi tại{" "}
          <Link to="/bookings" className="font-medium underline">
            Lịch xem của tôi
          </Link>
          .
        </Notice>
      )}

      {book.isError && (
        <ErrorBox error={book.error} />
      )}
      {book.error instanceof ApiError && book.error.code === "SLOT_UNAVAILABLE" && (
        <p className="text-xs text-muted">Giờ này vừa có người đặt — hãy tìm lại giờ xem.</p>
      )}

      {!user && (
        <Link to="/login" state={{ from: location.pathname }} className="btn-primary w-full">
          Đăng nhập để đặt lịch
        </Link>
      )}
      {user && user.role !== "CUSTOMER" && <Notice>Chỉ tài khoản người mua mới đặt được lịch xem.</Notice>}
      {user?.role === "CUSTOMER" && (
        <>
          <div>
            <label htmlFor="note" className="label">
              Ghi chú cho chủ căn (không bắt buộc)
            </label>
            <textarea
              id="note"
              rows={2}
              maxLength={1000}
              className="input"
              placeholder="VD: Đi cùng 2 người"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <ViewingTimePicker
            propertyId={propertyId}
            busy={book.isPending}
            submitLabel="Gửi yêu cầu xem nhà"
            onPick={(startAt, windows) => book.mutate({ startAt, windows })}
          />
          <p className="text-xs text-muted">
            Chủ căn xác nhận thì lịch mới có hiệu lực; khi đó căn được giữ riêng cho bạn đúng trong khung giờ xem. Chủ căn chỉ thấy mã
            người mua và khoảng ngân sách, không thấy số điện thoại của bạn.
          </p>
        </>
      )}
    </aside>
  );
}
