import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { api, call } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { isGuest } from "./guest";
import { ErrorBox, Spinner } from "../components/ui";
import { bedroomsLabel, DIRECTION, formatArea, formatVnd, FURNISHING, LEGAL, PROPERTY_TYPE, VIEW } from "../lib/format";
import { BackLink, featureLine, imagesOf, PropertyImage } from "./shared";

/** Wireframe 1.4: property detail with gallery and the "book a viewing" call to action. */
export function BuyerPropertyPage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const [active, setActive] = useState(0);
  const property = useQuery({
    queryKey: ["property", id],
    queryFn: () => call(api.GET("/api/v1/properties/{property_id}", { params: { path: { property_id: id } } })),
  });

  if (property.isPending) return <Spinner />;
  if (property.isError) return <ErrorBox error={property.error} onRetry={() => property.refetch()} />;
  const p = property.data;
  const images = imagesOf(p);
  const thumbs = images.slice(0, 4);
  const more = images.length - thumbs.length;
  const schedulePath = `/buyer/properties/${p.id}/schedule`;

  return (
    <div className="space-y-4">
      <BackLink to="/buyer/chat">Quay lại AI Agent</BackLink>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-2">
          <PropertyImage src={images[active]?.url} alt={`Ảnh căn ${p.unit_code}`} className="aspect-[4/3] w-full rounded-2xl" />
          {thumbs.length > 1 && (
            <div className="grid grid-cols-5 gap-2">
              {thumbs.map((m, i) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setActive(i)}
                  aria-label={`Ảnh ${i + 1}`}
                  aria-pressed={active === i}
                  className={`overflow-hidden rounded-lg ring-2 ${active === i ? "ring-brand-600" : "ring-transparent"}`}
                >
                  <PropertyImage src={m.url} alt="" className="aspect-square w-full" />
                </button>
              ))}
              {more > 0 && (
                <span className="grid aspect-square place-items-center rounded-lg bg-slate-800 text-sm font-medium text-white">+{more} ảnh</span>
              )}
            </div>
          )}
        </div>

        <section className="card h-fit space-y-5 p-6 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold">{p.unit_code}</h1>
            <p className="text-sm text-muted">{p.project_name}</p>
            <p className="mt-3 text-3xl font-bold text-ink">{formatVnd(p.price_vnd)}</p>
            <p className="mt-2 text-sm">
              {bedroomsLabel(p.bedrooms)} · {formatArea(p.area_m2)} · Tầng {p.floor} · {p.building_name}
            </p>
            <p className="text-sm text-muted">{featureLine(p)}</p>
          </div>

          <div>
            <h2 className="mb-2 font-semibold">Thông tin chi tiết</h2>
            <dl className="text-sm">
              <Row label="Dự án" value={p.project_name} />
              <Row label="Loại căn" value={`${PROPERTY_TYPE[p.property_type]} ${bedroomsLabel(p.bedrooms)}`} />
              <Row label="Diện tích" value={formatArea(p.area_m2)} />
              <Row label="Tầng" value={String(p.floor)} />
              <Row label="Hướng" value={DIRECTION[p.direction]} />
              <Row label="View" value={VIEW[p.view]} />
              <Row label="Nội thất" value={FURNISHING[p.furnishing]} />
              <Row label="Phòng tắm" value={String(p.bathrooms)} />
              <Row label="Pháp lý" value={LEGAL[p.legal_status]} />
            </dl>
            {p.description && <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-muted">{p.description}</p>}
          </div>

          {/* Buyers and guests pick a time; anyone else is first asked whether they are new or returning */}
          <Link
            to={user?.role === "CUSTOMER" || (!user && isGuest()) ? schedulePath : "/buyer/start"}
            className="btn-primary w-full rounded-xl py-3 text-base"
          >
            Đặt lịch xem căn này
          </Link>
          <p className="text-xs text-muted">Chủ căn chỉ thấy mã người mua và khoảng ngân sách, không thấy số điện thoại của bạn.</p>
        </section>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-3 border-b border-line py-2 last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
