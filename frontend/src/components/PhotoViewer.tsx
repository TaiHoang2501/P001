import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import type { Media, Property } from "../api/types";
import {
  bedroomsLabel,
  DIRECTION,
  formatArea,
  formatVnd,
  FURNISHING,
  LEGAL,
  PROPERTY_STATUS,
  VIEW,
} from "../lib/format";

/**
 * Full-screen photo viewer: previous / next buttons (and ← → keys), a counter, thumbnails; Esc or a click
 * outside the photo closes it. `info` is shown under the photo (e.g. the home's details). Rendered at the
 * page root so it covers the whole window.
 */
export function PhotoViewer({
  images,
  start,
  title,
  info,
  onClose,
}: {
  images: Media[];
  start: number;
  title: string;
  info?: ReactNode;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(start);
  const count = images.length;
  const go = (step: number) => setIndex((i) => (i + step + count) % count);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    document.addEventListener("keydown", onKey);
    // The page behind must not scroll while the photos are open
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const arrow =
    "absolute top-1/2 grid size-12 -translate-y-1/2 place-items-center rounded-full bg-white/15 text-3xl text-white backdrop-blur transition hover:bg-white/30 md:size-14";

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/95 animate-rise-in"
      role="dialog"
      aria-modal="true"
      aria-label={`Ảnh căn ${title}`}
      onClick={onClose}
    >
      <div className="flex items-center justify-between px-5 py-4 text-white" onClick={(e) => e.stopPropagation()}>
        <p className="font-semibold">
          Căn {title}{" "}
          <span className="ml-2 text-sm text-white/70">
            {index + 1} / {count}
          </span>
        </p>
        <button
          type="button"
          onClick={onClose}
          className="grid size-10 place-items-center rounded-full text-2xl hover:bg-white/15"
          aria-label="Đóng"
          autoFocus
        >
          ✕
        </button>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center px-3 sm:px-16 md:px-24">
        <img
          key={images[index].url}
          src={images[index].url}
          alt={`Ảnh ${index + 1} của căn ${title}`}
          className="max-h-full max-w-full animate-rise-in rounded-xl object-contain shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        />
        {count > 1 && (
          <>
            <button
              type="button"
              className={`${arrow} left-3 md:left-6`}
              aria-label="Ảnh trước"
              onClick={(e) => {
                e.stopPropagation();
                go(-1);
              }}
            >
              ‹
            </button>
            <button
              type="button"
              className={`${arrow} right-3 md:right-6`}
              aria-label="Ảnh sau"
              onClick={(e) => {
                e.stopPropagation();
                go(1);
              }}
            >
              ›
            </button>
          </>
        )}
      </div>

      {info && (
        <div className="px-4 pt-4" onClick={(e) => e.stopPropagation()}>
          {info}
        </div>
      )}

      {count > 1 && (
        <div className="flex justify-center gap-2 overflow-x-auto px-5 py-4" onClick={(e) => e.stopPropagation()}>
          {images.map((m, i) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Ảnh ${i + 1}`}
              aria-current={i === index}
              className={`h-14 w-20 shrink-0 overflow-hidden rounded-lg ring-2 transition ${
                i === index ? "opacity-100 ring-white" : "opacity-50 ring-transparent hover:opacity-80"
              }`}
            >
              <img src={m.url} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
      {count <= 1 && <div className="h-4" />}
    </div>,
    document.body,
  );
}

/** The home's details under its photos: code, status, price, where it is and its main facts. */
export function PropertyPhotoInfo({ property: p }: { property: Property }) {
  const facts: [string, string][] = [
    ["Diện tích", formatArea(p.area_m2)],
    ["Phòng ngủ", bedroomsLabel(p.bedrooms)],
    ["Phòng tắm", `${p.bathrooms} WC`],
    ["Tầng", String(p.floor)],
    ["Hướng", DIRECTION[p.direction]],
    ["View", VIEW[p.view]],
    ["Nội thất", FURNISHING[p.furnishing]],
    ["Pháp lý", LEGAL[p.legal_status]],
  ];
  return (
    <section
      className="mx-auto max-w-4xl rounded-3xl bg-white/10 p-3.5 text-white ring-1 ring-white/15 backdrop-blur sm:p-5"
      aria-label={`Thông tin căn ${p.unit_code}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-display text-lg font-bold sm:text-xl">{p.unit_code}</span>
            <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-semibold">
              {PROPERTY_STATUS[p.status]}
            </span>
          </p>
          <p className="truncate text-sm text-white/70">
            {p.building_name} · {p.project_name}
            {p.city && ` · ${p.city}`}
          </p>
        </div>
        <p className="font-display text-xl font-bold sm:text-2xl">{formatVnd(p.price_vnd)}</p>
      </div>
      <dl className="mt-2.5 grid grid-cols-4 gap-x-3 gap-y-1.5 sm:mt-3 sm:gap-x-4 sm:gap-y-2">
        {facts.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="truncate text-[10px] uppercase tracking-wide text-white/55 sm:text-[11px]">{label}</dt>
            <dd className="truncate text-xs font-semibold sm:text-sm">{value}</dd>
          </div>
        ))}
      </dl>
      {p.description && <p className="mt-3 line-clamp-2 hidden text-sm text-white/75 sm:block">{p.description}</p>}
    </section>
  );
}
