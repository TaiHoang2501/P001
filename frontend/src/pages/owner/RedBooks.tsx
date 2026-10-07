import { useState } from "react";
import { Link } from "react-router";

import type { OwnershipVerification, Property } from "../../api/types";
import { Spinner } from "../../components/ui";
import { formatArea, formatDateTime, formatVnd, PROPERTY_STATUS } from "../../lib/format";
import { imagesOf, PropertyImage } from "../../buyer/shared";
import { PhotoViewer, PropertyPhotoInfo } from "../../components/PhotoViewer";
import { useOwnerProperties, useRedBooks } from "./ownerData";

/** Listing status colours: green on sale, amber waiting for the investor, red sent back, grey off sale. */
const BADGE: Record<Property["status"], string> = {
  AVAILABLE: "bg-leaf text-leaf-ink",
  PENDING_REVIEW: "bg-amber-100 text-amber-900 ring-1 ring-amber-300",
  DRAFT: "bg-amber-100 text-amber-900 ring-1 ring-amber-300",
  REJECTED: "bg-red-100 text-red-800 ring-1 ring-red-300",
  WITHDRAWN: "bg-sand text-muted",
  SOLD: "bg-sand text-muted",
};

/** 1 for a listing not approved yet (shown after the ones on sale), else 0. */
const waiting = (p?: Property) => (p && ["PENDING_REVIEW", "REJECTED", "DRAFT"].includes(p.status) ? 1 : 0);

/**
 * The seller's verified red books as cards, in two groups: homes already listed (with their photo, price and
 * listing status) and red books not listed yet (a way to list them now).
 */
export function RedBookList() {
  const books = useRedBooks();
  const listings = useOwnerProperties();
  const byId = new Map((listings.data ?? []).map((p) => [p.id, p]));
  const verified = (books.data ?? []).filter((b) => b.status === "VERIFIED");
  const listed = verified.filter((b) => b.property_id != null);
  const unlisted = verified.filter((b) => b.property_id == null);

  if (books.isPending) return <Spinner />;
  if (verified.length === 0) {
    return (
      <p className="rounded-3xl bg-paper px-5 py-8 text-center text-muted">
        Bạn chưa xác thực sổ đỏ nào.{" "}
        <Link to="/owner/verify" className="font-semibold text-brand-700 underline">
          Xác thực sổ đỏ
        </Link>{" "}
        để bắt đầu đăng bán.
      </p>
    );
  }
  return (
    <div className="space-y-8">
      {listed.length > 0 && (
        <section>
          <GroupTitle title="Đã đăng bán" count={listed.length} hint="Sổ đỏ đã gắn với tin đăng" />
          <ul className="grid gap-4 sm:grid-cols-2">
            {/* On sale first; listings still waiting for the investor (or sent back) at the end */}
            {[...listed]
              .sort((a, b) => waiting(byId.get(a.property_id!)) - waiting(byId.get(b.property_id!)))
              .map((b) => (
                <ListedBook key={b.id} book={b} listing={byId.get(b.property_id!)} />
              ))}
          </ul>
        </section>
      )}
      {unlisted.length > 0 && (
        <section>
          <GroupTitle title="Chưa đăng bán" count={unlisted.length} hint="Đã xác thực, bạn có thể đăng bán ngay" />
          <ul className="grid gap-3 sm:grid-cols-2">
            {unlisted.map((b) => (
              <UnlistedBook key={b.id} book={b} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function GroupTitle({ title, count, hint }: { title: string; count: number; hint: string }) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline gap-x-3">
      <h3 className="font-display text-xl font-bold">
        {title} <span className="text-muted">· {count}</span>
      </h3>
      <span className="text-sm text-muted">{hint}</span>
    </div>
  );
}

/** Code, holder and date of a red book, with the "verified" seal. */
function BookFacts({ book: b }: { book: OwnershipVerification }) {
  return (
    <div className="flex items-start gap-2.5 rounded-2xl bg-canvas/70 px-3 py-2.5">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-leaf text-leaf-ink" aria-hidden="true">
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2">
          <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" strokeLinejoin="round" />
          <path d="M8.5 12l2.5 2.5 4.5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <div className="min-w-0 text-sm">
        <p className="font-mono font-semibold">{b.red_book_code}</p>
        <p className="truncate text-muted">
          {b.red_book_holder_name}
          {b.verified_at && ` · xác thực ${formatDateTime(b.verified_at)}`}
        </p>
      </div>
    </div>
  );
}

/** A red book behind a listing: the home's photo, what it is and how the listing stands. */
function ListedBook({ book: b, listing: p }: { book: OwnershipVerification; listing?: Property }) {
  const images = p ? imagesOf(p) : [];
  const [viewer, setViewer] = useState<number | null>(null);
  return (
    <li className="flex flex-col overflow-hidden rounded-[28px] bg-paper">
      <div className="relative">
        <button
          type="button"
          className="group block w-full overflow-hidden disabled:cursor-default"
          disabled={images.length === 0}
          onClick={() => setViewer(0)}
          aria-label={p ? `Xem ${images.length} ảnh căn ${p.unit_code}` : "Ảnh căn"}
        >
          <PropertyImage
            src={images[0]?.url}
            alt={p ? `Ảnh căn ${p.unit_code}` : ""}
            className="aspect-[16/9] w-full transition duration-300 group-hover:scale-105"
          />
        </button>
        {images.length > 0 && (
          <span className="pointer-events-none absolute bottom-3 right-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
            ⤢ {images.length} ảnh
          </span>
        )}
        {p && viewer !== null && (
          <PhotoViewer
            images={images}
            start={viewer}
            title={p.unit_code}
            info={<PropertyPhotoInfo property={p} />}
            onClose={() => setViewer(null)}
          />
        )}
        {p && (
          <span className={`absolute left-3 top-3 rounded-full px-3 py-1 text-xs font-semibold shadow-sm ${BADGE[p.status]}`}>
            Đã đăng · {PROPERTY_STATUS[p.status].toLowerCase()}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        {p ? (
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="font-display text-xl font-bold leading-tight">{p.unit_code}</p>
              <p className="truncate text-sm text-muted">
                {p.building_name} · {p.project_name}
              </p>
              <p className="text-sm">
                {formatArea(p.area_m2)} · {p.bedrooms === 0 ? "Studio" : `${p.bedrooms} PN`} · Tầng {p.floor}
              </p>
            </div>
            <p className="shrink-0 font-display text-xl font-bold text-brand-700">{formatVnd(p.price_vnd)}</p>
          </div>
        ) : (
          <p className="font-display text-xl font-bold">Tin #{b.property_id}</p>
        )}
        <BookFacts book={b} />
        {p && p.status !== "SOLD" && (
          <Link
            to={`/owner/properties/${p.id}/slots`}
            className="mt-auto w-fit rounded-full border border-ink/15 px-4 py-2 text-sm font-bold hover:bg-sand"
          >
            Thay đổi khung giờ
          </Link>
        )}
      </div>
    </li>
  );
}

/** A verified red book with no listing yet: compact, a small red book (no photo of the home exists yet) and "list it". */
function UnlistedBook({ book: b }: { book: OwnershipVerification }) {
  return (
    <li className="flex items-center gap-4 rounded-[24px] bg-paper p-3 pr-4">
      <div className="grid h-24 w-20 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#f6d9c4] to-[#ecdcc4]">
        {/* Illustration of a red book (sổ đỏ) */}
        <svg viewBox="0 0 70 86" className="h-16 drop-shadow" aria-hidden="true">
          <rect x="9" y="5" width="54" height="76" rx="5" fill="#9b2a22" />
          <rect x="5" y="3" width="54" height="76" rx="5" fill="#c0392b" />
          <rect x="10" y="8" width="44" height="66" rx="3" fill="none" stroke="#f3c56b" strokeWidth="1.6" />
          <circle cx="32" cy="31" r="9" fill="none" stroke="#f3c56b" strokeWidth="1.8" />
          <path d="M32 25l1.8 3.7 4 .5-3 2.8.8 4-3.6-2-3.6 2 .8-4-3-2.8 4-.5z" fill="#f3c56b" />
          <rect x="17" y="49" width="30" height="3.2" rx="1.6" fill="#f3c56b" />
          <rect x="21" y="56" width="22" height="2.6" rx="1.3" fill="#f3c56b" opacity="0.8" />
        </svg>
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-mono text-sm font-bold">{b.red_book_code}</p>
        <p className="truncate text-sm text-muted">
          {b.red_book_holder_name}
          {b.verified_at && ` · xác thực ${formatDateTime(b.verified_at)}`}
        </p>
        {b.unit && (
          <p className="truncate text-sm">
            Căn <strong>{b.unit.unit_code}</strong> · {b.unit.building_name} · {formatArea(b.unit.area_m2)} ·{" "}
            {b.unit.bedrooms === 0 ? "Studio" : `${b.unit.bedrooms} PN`} · Tầng {b.unit.floor}
          </p>
        )}
        <p className="mt-1 flex items-center gap-1 text-xs font-semibold text-leaf-ink">
          <svg viewBox="0 0 24 24" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
            <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Đã xác thực · chưa đăng bán
        </p>
      </div>
      <Link
        to={`/owner/properties/new?verification=${b.id}`}
        className="shrink-0 rounded-full bg-brand-600 px-4 py-2 font-display text-sm font-bold text-canvas hover:bg-brand-700"
      >
        Đăng bán
      </Link>
    </li>
  );
}
