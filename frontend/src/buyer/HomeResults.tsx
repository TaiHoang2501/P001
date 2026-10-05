import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { api, call } from "../api/client";
import type { CriterionMatch, Media, Property, Recommendation } from "../api/types";
import { ErrorBox, Spinner } from "../components/ui";
import {
  DIRECTION,
  formatArea,
  formatTimeRange,
  formatVnd,
  FURNISHING,
  LEGAL,
  PROPERTY_TYPE,
  vnIso,
  vnToday,
  VIEW,
} from "../lib/format";
import { useProperty } from "./PropertyDetailCard";
import { imagesOf, PropertyImage } from "./shared";

export type Need = { label: string; value: string };

type Check = { ok: boolean; text: string };

/** How a home meets each thing the buyer asked for, in plain words ("✓ 2 phòng ngủ", "✕ Tầng 8 (muốn 15–20)"). */
export function matchChecks(rec: Recommendation, project?: string): Check[] {
  const p = rec.property;
  const say = (m: CriterionMatch): string => {
    const wish = m.matched ? "" : ` (bạn muốn ${m.wanted})`;
    switch (m.criterion) {
      case "bedrooms":
        return p.bedrooms === 0 ? `Studio${wish}` : `${p.bedrooms} phòng ngủ${wish}`;
      case "price":
        return `${formatVnd(p.price_vnd)}, trong ngân sách`;
      case "area":
        return `${formatArea(p.area_m2)}${wish}`;
      case "direction":
        return `Hướng ${DIRECTION[p.direction]}${m.matched ? "" : " (khác hướng bạn muốn)"}`;
      case "view":
        return `View ${VIEW[p.view].toLowerCase()}${m.matched ? "" : " (khác view bạn muốn)"}`;
      case "floor":
        return `Tầng ${p.floor}${wish}`;
      case "furnishing":
        return `${FURNISHING[p.furnishing]}${m.matched ? "" : " (khác yêu cầu)"}`;
      default:
        return `${m.criterion}: ${m.actual}`;
    }
  };
  return [
    ...rec.matched.map((m) => ({ ok: true, text: say(m) })),
    ...(project ? [{ ok: true, text: p.project_name }] : []),
    ...rec.unmatched.map((m) => ({ ok: false, text: say(m) })),
  ];
}

function Checks({ checks, limit }: { checks: Check[]; limit?: number }) {
  const shown = limit ? checks.slice(0, limit) : checks;
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
      {shown.map((c) => (
        <li key={c.text} className={c.ok ? "text-leaf-ink" : "text-brand-700"}>
          {c.ok ? "✓" : "✕"} {c.text}
        </li>
      ))}
    </ul>
  );
}

function Score({ score }: { score: number }) {
  return (
    <span className="shrink-0 rounded-full bg-leaf px-2 py-0.5 text-[11px] font-bold text-leaf-ink">
      Khớp {Math.round(score * 100)}%
    </span>
  );
}

/**
 * The right-hand panel: what the buyer asked for (removable chips) and the matching homes as small cards,
 * so many fit on screen; each card still says why it matches.
 */
export function ResultsList({
  recommendations,
  needs,
  onOpen,
  onRemoveNeed,
  onAddNeed,
}: {
  recommendations: Recommendation[];
  needs: Need[];
  onOpen: (id: number, code?: string) => void;
  onRemoveNeed?: (need: Need) => void;
  onAddNeed: () => void;
}) {
  const project = needs.find((n) => n.label === "Dự án")?.value;
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pb-3 pt-5 md:px-7">
        <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Nhu cầu của bạn</h2>
        <ul className="mt-2.5 flex flex-wrap gap-2">
          {needs.map((n) => (
            <li key={n.label} className="flex items-center gap-1 rounded-full bg-leaf py-1 pl-3 pr-1.5 text-[13px] font-semibold text-leaf-ink">
              <span title={n.label}>{n.value}</span>
              {onRemoveNeed && (
                <button
                  type="button"
                  className="grid size-5 place-items-center rounded-full hover:bg-black/10"
                  aria-label={`Bỏ tiêu chí ${n.value}`}
                  onClick={() => onRemoveNeed(n)}
                >
                  ✕
                </button>
              )}
            </li>
          ))}
          <li>
            <button
              type="button"
              className="rounded-full border border-ink/15 px-3 py-1 text-[13px] font-semibold hover:bg-sand"
              onClick={onAddNeed}
            >
              + Thêm tiêu chí
            </button>
          </li>
        </ul>
        <div className="mt-4 flex items-baseline justify-between gap-3">
          <h2 className="font-display text-2xl font-bold">{recommendations.length} căn phù hợp</h2>
          <span className="text-xs text-muted">Xếp theo mức khớp</span>
        </div>
      </div>
      <ul className="grid flex-1 content-start gap-3 overflow-y-auto px-5 pb-5 md:px-7 xl:grid-cols-2">
        {recommendations.map((r) => (
          <li key={r.property.id}>
            <HomeCard rec={r} project={project} onOpen={onOpen} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A compact home card: enough to compare at a glance, with how it meets the buyer's needs. */
export function HomeCard({
  rec,
  project,
  onOpen,
}: {
  rec: Recommendation;
  project?: string;
  onOpen: (id: number, code?: string) => void;
}) {
  const p = rec.property;
  const scored = rec.matched.length + rec.unmatched.length > 0;
  return (
    <article className="flex gap-3 rounded-2xl bg-canvas p-3 transition hover:shadow-md">
      <PropertyImage src={imagesOf(p)[0]?.url} alt={`Căn ${p.unit_code}`} className="size-20 shrink-0 rounded-xl" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate font-display text-lg font-bold leading-tight">{p.unit_code}</h3>
          {scored && <Score score={rec.match_score} />}
        </div>
        <p className="truncate text-xs text-muted">
          {p.building_name} · {p.project_name}
        </p>
        <p className="text-xs">
          {p.bedrooms === 0 ? "Studio" : `${p.bedrooms} PN`} · {p.bathrooms} WC · {formatArea(p.area_m2)} · Tầng {p.floor} ·{" "}
          {DIRECTION[p.direction]}
        </p>
        {scored && <Checks checks={matchChecks(rec, project)} limit={4} />}
        <div className="mt-auto flex items-end justify-between gap-2 pt-1">
          <div>
            <p className="font-display text-xl font-bold leading-none">{formatVnd(p.price_vnd)}</p>
            <p className="mt-0.5 text-[11px] font-semibold text-leaf-ink">✓ Chủ căn đã xác thực</p>
          </div>
          <button
            type="button"
            className="rounded-full bg-brand-600 px-4 py-1.5 font-display text-sm font-bold text-canvas hover:bg-brand-700"
            onClick={() => onOpen(p.id, p.unit_code)}
          >
            Xem chi tiết
          </button>
        </div>
      </div>
    </article>
  );
}

/** The next free viewing times of a home (seller's slots, 08:00–20:00 over the coming week). */
function useNextTimes(propertyId: number) {
  return useQuery({
    queryKey: ["next-times", propertyId],
    queryFn: () =>
      call(
        api.POST("/api/v1/properties/{property_id}/viewing-times", {
          params: { path: { property_id: propertyId } },
          body: { windows: [{ start_at: vnIso(vnToday(1), "08:00"), end_at: vnIso(vnToday(7), "20:00") }] },
        }),
      ),
  });
}

/** Everything about one home, in the right-hand panel (design: detail view), with booking at the bottom. */
export function HomeDetail({
  propertyId,
  rec,
  project,
  onBack,
  onBook,
}: {
  propertyId: number;
  rec?: Recommendation;
  project?: string;
  onBack: () => void;
  onBook: (p: Property) => void;
}) {
  const property = useProperty(propertyId);
  const times = useNextTimes(propertyId);
  // Index of the photo open full screen, or null
  const [viewer, setViewer] = useState<number | null>(null);

  if (property.isPending) return <Spinner label="Đang tải thông tin căn..." />;
  if (property.isError) return <ErrorBox error={property.error} onRetry={() => property.refetch()} />;
  const p = property.data;
  const images = imagesOf(p);
  const perM2 = Math.round(p.price_vnd / Number(p.area_m2) / 1_000_000);
  const slots = (times.data?.proposals.length ? times.data.proposals : (times.data?.alternatives ?? [])).slice(0, 3);
  const specs: [string, string][] = [
    ["Diện tích", formatArea(p.area_m2)],
    ["Phòng", `${p.bedrooms === 0 ? "Studio" : `${p.bedrooms} PN`} · ${p.bathrooms} WC`],
    ["Tầng", `Tầng ${p.floor}`],
    ["Hướng", DIRECTION[p.direction]],
    ["View", VIEW[p.view]],
    ["Nội thất", FURNISHING[p.furnishing]],
  ];

  return (
    <div className="relative flex h-full flex-col">
      <div className="flex-1 space-y-5 overflow-y-auto px-5 pb-28 pt-5 md:px-7">
        <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:underline">
          ← Danh sách căn
        </button>

        {/* Photos: one large, two small; any of them opens the full-screen viewer */}
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          <button
            type="button"
            className="group relative overflow-hidden rounded-3xl"
            onClick={() => images.length > 0 && setViewer(0)}
            aria-label={images.length > 0 ? `Xem ${images.length} ảnh của căn ${p.unit_code}` : undefined}
            disabled={images.length === 0}
          >
            <PropertyImage
              src={images[0]?.url}
              alt={`Ảnh căn ${p.unit_code}`}
              className="aspect-[16/10] h-full w-full transition duration-300 group-hover:scale-[1.02] sm:aspect-auto sm:min-h-72"
            />
            {images.length > 0 && (
              <span className="absolute bottom-3 left-3 rounded-full bg-black/55 px-3 py-1 text-xs font-semibold text-white">
                ⤢ Xem {images.length} ảnh
              </span>
            )}
          </button>
          <div className="hidden grid-rows-2 gap-3 sm:grid">
            {[1, 2].map((i) =>
              images[i] ? (
                <button
                  key={i}
                  type="button"
                  onClick={() => setViewer(i)}
                  className="group relative overflow-hidden rounded-3xl"
                  aria-label={`Ảnh ${i + 1}`}
                >
                  <PropertyImage src={images[i].url} alt="" className="h-full w-full transition duration-300 group-hover:scale-[1.04]" />
                  {i === 2 && images.length > 3 && (
                    <span className="absolute inset-0 grid place-items-center bg-black/40 font-display text-2xl font-bold text-white">
                      +{images.length - 3}
                    </span>
                  )}
                </button>
              ) : (
                <div key={i} className="grid place-items-center rounded-3xl bg-sand text-xs text-muted">
                  {i === 1 ? "Chưa có thêm ảnh" : "Chưa có mặt bằng"}
                </div>
              ),
            )}
          </div>
        </div>
        {viewer !== null && (
          <PhotoViewer images={images} start={viewer} title={p.unit_code} onClose={() => setViewer(null)} />
        )}

        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            {rec && rec.matched.length + rec.unmatched.length > 0 && (
              <span className="rounded-full bg-leaf px-2.5 py-0.5 text-xs font-bold text-leaf-ink">
                Khớp {Math.round(rec.match_score * 100)}% với nhu cầu
              </span>
            )}
            <h2 className="mt-1 font-display text-4xl font-bold leading-tight">{p.unit_code}</h2>
            <p className="text-sm text-muted">
              {p.building_name} · {p.project_name} · {PROPERTY_TYPE[p.property_type]}
            </p>
          </div>
          <div className="text-right">
            <p className="font-display text-3xl font-bold text-brand-700">{formatVnd(p.price_vnd)}</p>
            {Number.isFinite(perM2) && <p className="text-xs text-muted">≈ {perM2} tr/m²</p>}
          </div>
        </div>

        <div className="flex items-start gap-3 rounded-2xl bg-leaf/70 px-4 py-3">
          <svg viewBox="0 0 24 24" className="mt-0.5 size-6 shrink-0 text-leaf-ink" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" strokeLinejoin="round" />
            <path d="M8.5 12l2.5 2.5 4.5-5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <p className="font-semibold text-leaf-ink">Chủ căn và pháp lý đã được Vinhomes xác thực</p>
            <p className="text-sm text-leaf-ink">{LEGAL[p.legal_status]} · tin đăng đã được Chủ đầu tư duyệt</p>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {specs.map(([label, value]) => (
            <div key={label} className="rounded-2xl bg-canvas px-4 py-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="font-semibold">{value}</dd>
            </div>
          ))}
        </dl>

        {p.description && <p className="whitespace-pre-line text-sm leading-relaxed text-ink/80">{p.description}</p>}

        {rec && rec.matched.length + rec.unmatched.length > 0 && (
          <section>
            <h3 className="mb-2 font-display text-lg font-bold">Vì sao căn này phù hợp</h3>
            <Checks checks={matchChecks(rec, project)} />
          </section>
        )}

        <section>
          <h3 className="mb-2 font-display text-lg font-bold">Lịch trống gần nhất</h3>
          {times.isPending && <p className="text-sm text-muted">Đang xem lịch của chủ căn...</p>}
          {times.data && slots.length === 0 && <p className="text-sm text-muted">Chủ căn chưa mở lịch xem trong tuần tới.</p>}
          <div className="flex flex-wrap gap-2">
            {slots.map((s) => (
              <button
                key={s.start_at}
                type="button"
                onClick={() => onBook(p)}
                className="rounded-full border border-ink/15 bg-canvas px-4 py-2 text-sm font-semibold hover:border-brand-500 hover:text-brand-700"
              >
                {formatTimeRange(s.start_at, s.end_at)}
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* Always in view: the home, its price and the booking button */}
      <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-3 rounded-b-[28px] border-t border-line bg-sand/95 px-5 py-3 backdrop-blur md:px-7">
        <div className="min-w-0 flex-1">
          <p className="truncate font-display font-bold">
            {p.unit_code} · {formatVnd(p.price_vnd)}
          </p>
          <p className="text-xs text-muted">Chủ căn chỉ thấy mã người mua và khoảng ngân sách của bạn.</p>
        </div>
        <button
          type="button"
          onClick={() => onBook(p)}
          className="rounded-full bg-brand-600 px-6 py-2.5 font-display text-base font-bold text-canvas shadow-sm hover:bg-brand-700"
        >
          Đặt lịch xem
        </button>
      </div>
    </div>
  );
}

/**
 * Full-screen photo viewer: previous / next buttons (and ← → keys), a counter, thumbnails; Esc or a click
 * outside the photo closes it. Rendered at the page root so it covers the whole window.
 */
function PhotoViewer({
  images,
  start,
  title,
  onClose,
}: {
  images: Media[];
  start: number;
  title: string;
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
  }, []);

  const arrow =
    "absolute top-1/2 grid size-12 -translate-y-1/2 place-items-center rounded-full bg-white/15 text-3xl text-white backdrop-blur transition hover:bg-white/30 md:size-14";

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/90 animate-rise-in"
      role="dialog"
      aria-modal="true"
      aria-label={`Ảnh căn ${title}`}
      onClick={onClose}
    >
      <div className="flex items-center justify-between px-5 py-4 text-white" onClick={(e) => e.stopPropagation()}>
        <p className="font-semibold">
          Căn {title} <span className="ml-2 text-sm text-white/70">{index + 1} / {count}</span>
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

      <div className="relative flex min-h-0 flex-1 items-center justify-center px-16 md:px-24">
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
    </div>,
    document.body,
  );
}
