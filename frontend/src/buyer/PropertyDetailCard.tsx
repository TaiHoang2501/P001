import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../api/client";
import type { Property } from "../api/types";
import { ErrorBox, Spinner } from "../components/ui";
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
import { BackButton, featureLine, imagesOf, PropertyImage } from "./shared";

export function useProperty(propertyId: number) {
  return useQuery({
    queryKey: ["property", propertyId],
    queryFn: () =>
      call(
        api.GET("/api/v1/properties/{property_id}", {
          params: { path: { property_id: propertyId } },
        }),
      ),
  });
}

/** Wireframe 1.4, shown inside the agent chat: photos, facts and the "book a viewing" action. */
export function PropertyDetailCard({
  propertyId,
  onBook,
  onBack,
}: {
  propertyId: number;
  onBook: (p: Property) => void;
  onBack?: () => void;
}) {
  const property = useProperty(propertyId);
  const [active, setActive] = useState(0);

  if (property.isPending) return <Spinner label="Đang tải thông tin căn..." />;
  if (property.isError)
    return (
      <ErrorBox error={property.error} onRetry={() => property.refetch()} />
    );
  const p = property.data;
  const images = imagesOf(p);
  const thumbs = images.slice(0, 4);
  const more = images.length - thumbs.length;

  return (
    <article
      // Laid out by its own width (@container): stacked in the narrow side panel, two columns when wide
      className="card @container w-full shadow-sm"
      aria-label={`Chi tiết căn ${p.unit_code}`}
    >
      {onBack && (
        <div className="px-3 pt-3">
          <BackButton onClick={onBack}>Quay lại</BackButton>
        </div>
      )}
      <div className="grid gap-0 @2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-2 p-3">
          <PropertyImage
            src={images[active]?.url}
            alt={`Ảnh căn ${p.unit_code}`}
            className="aspect-[2/1] w-full rounded-xl @2xl:aspect-[4/3]"
          />
          {thumbs.length > 1 && (
            <div className="grid grid-cols-5 gap-1.5">
              {thumbs.map((m, i) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setActive(i)}
                  aria-label={`Ảnh ${i + 1}`}
                  aria-pressed={active === i}
                  className={`overflow-hidden rounded-md ring-2 ${active === i ? "ring-brand-600" : "ring-transparent"}`}
                >
                  <PropertyImage
                    src={m.url}
                    alt=""
                    className="aspect-square w-full"
                  />
                </button>
              ))}
              {more > 0 && (
                <span className="grid aspect-square place-items-center rounded-md bg-slate-800 text-xs font-medium text-white">
                  +{more}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3 p-4">
          <div>
            <h3 className="text-xl font-bold">{p.unit_code}</h3>
            <p className="text-sm text-muted">
              {p.project_name} · {p.building_name}
            </p>
            <p className="mt-2 text-2xl font-bold">{formatVnd(p.price_vnd)}</p>
            <p className="text-sm">
              {bedroomsLabel(p.bedrooms)} · {formatArea(p.area_m2)} · Tầng{" "}
              {p.floor}
            </p>
            <p className="text-sm text-muted">{featureLine(p)}</p>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 text-sm">
            <Row label="Loại căn" value={PROPERTY_TYPE[p.property_type]} />
            <Row label="Hướng" value={DIRECTION[p.direction]} />
            <Row label="View" value={VIEW[p.view]} />
            <Row label="Nội thất" value={FURNISHING[p.furnishing]} />
            <Row label="Phòng tắm" value={String(p.bathrooms)} />
            <Row label="Pháp lý" value={LEGAL[p.legal_status]} />
          </dl>
          {p.description && (
            <p className="whitespace-pre-line text-sm leading-relaxed text-muted">
              {p.description}
            </p>
          )}
          {/* Stays in view at the bottom of the side panel while the details scroll */}
          <div className="sticky bottom-0 -mx-4 -mb-4 space-y-2 rounded-b-xl bg-white px-4 pb-4 pt-2">
            <button
              type="button"
              className="btn-primary w-full rounded-xl py-2.5"
              onClick={() => onBook(p)}
            >
              Đặt lịch xem căn này
            </button>
            <p className="text-xs text-muted">
              Chủ căn chỉ thấy mã người mua và khoảng ngân sách, không thấy số
              điện thoại của bạn.
            </p>
          </div>
        </div>
      </div>
    </article>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-b border-line py-1.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
