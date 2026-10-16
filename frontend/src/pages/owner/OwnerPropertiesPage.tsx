import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import { Link, useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import { useJumpFlash } from "../../lib/jump";
import type { Property } from "../../api/types";
import { ErrorBox, Notice, Spinner } from "../../components/ui";
import { formatArea, formatVnd, PROPERTY_STATUS } from "../../lib/format";
import { imagesOf, PropertyImage } from "../../buyer/shared";
import { PhotoViewer, PropertyPhotoInfo } from "../../components/PhotoViewer";
import { usableRedBooks, useOwnerOverview, useOwnerProperties, useRedBooks } from "./ownerData";
import { PropertyFormPage } from "./PropertyFormPage";
import { RedBookList } from "./RedBooks";

type Tab = "listings" | "review" | "verified";

// Listings the investor has not approved yet: waiting for review, or rejected and to be fixed (there are no
// drafts: a listing goes for review when it is posted; DRAFT only covers older data)
const IN_REVIEW = new Set<Property["status"]>(["PENDING_REVIEW", "REJECTED", "DRAFT"]);
// The seller edits a listing while it waits for review, after a rejection, or while it is paused (as the API allows)
const EDITABLE = new Set<Property["status"]>([...IN_REVIEW, "WITHDRAWN"]);
type Stats = { viewing_requests: number; pending_requests: number; ai_suggestions: number; open_slots_week: number };

const STATUS_TONE: Record<Property["status"], string> = {
  AVAILABLE: "bg-leaf text-leaf-ink",
  PENDING_REVIEW: "bg-blush text-brand-900",
  DRAFT: "bg-sand text-muted",
  REJECTED: "bg-red-100 text-red-800",
  WITHDRAWN: "bg-sand text-muted",
  SOLD: "bg-sand text-muted",
};

/** "Căn của tôi": the seller's listings, and the red books they have verified (two sub-tabs). */
export function OwnerPropertiesPage() {
  const queryClient = useQueryClient();
  const list = useOwnerProperties();
  const overview = useOwnerOverview();
  const books = useRedBooks();
  const [params, setParams] = useSearchParams();
  // ?property=ID (from a notification about this listing): point at it
  const target = Number(params.get("property")) || null;
  const asked = params.get("tab");
  const listed = list.data?.find((p) => p.id === target);
  // A listing named in the link (?property=) opens the tab that holds it
  const tab: Tab = listed
    ? IN_REVIEW.has(listed.status)
      ? "review"
      : "listings"
    : asked === "verified" || asked === "review"
      ? asked
      : "listings";

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["owner-properties"] });
    queryClient.invalidateQueries({ queryKey: ["owner-overview"] });
  };
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
    mutationFn: ({ id, buyerId }: { id: number; buyerId: number | null }) =>
      call(api.POST("/api/v1/owner/properties/{property_id}/sold", { ...path(id), body: { buyer_id: buyerId } })),
    onSuccess: () => {
      setSelling(null);
      refresh();
      // The viewings it closed leave the bookings page too
      void queryClient.invalidateQueries({ queryKey: ["owner-bookings"] });
    },
  });
  // "Đánh dấu đã bán" cannot be undone: asked in a dialog that says so, not a quick browser prompt
  const [selling, setSelling] = useState<Property | null>(null);
  const actionError = submit.error ?? withdraw.error ?? sold.error;
  const busy = submit.isPending || withdraw.isPending || sold.isPending;

  const stats = new Map<number, Stats>((overview.data?.properties ?? []).map((s) => [s.property_id, s]));
  const all = list.data ?? [];
  const inReview = all.filter((p) => IN_REVIEW.has(p.status));
  const onSale = all.filter((p) => !IN_REVIEW.has(p.status));
  const shown = tab === "review" ? inReview : onSale;
  const verifiedCount = (books.data ?? []).filter((b) => b.status === "VERIFIED").length;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold">Căn của tôi</h1>
          <p className="text-muted">Tin đăng được Chủ đầu tư duyệt trước khi BookingBot gợi ý cho người mua.</p>
        </div>
        <Link
          to="/owner/properties/new"
          className="rounded-full bg-brand-600 px-6 py-3 font-display text-base font-bold text-canvas shadow-sm hover:bg-brand-700"
        >
          + Đăng bán căn
        </Link>
      </div>

      <div className="mb-5 flex w-fit rounded-full bg-sand p-1" role="tablist" aria-label="Căn của tôi">
        {(
          [
            ["listings", "Căn đăng bán", onSale.length],
            ["review", "Căn đang yêu cầu duyệt", inReview.length],
            ["verified", "Căn đã xác thực", verifiedCount],
          ] as const
        ).map(([key, label, count]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setParams(key === "listings" ? {} : { tab: key })}
            className={`rounded-full px-5 py-2 text-sm font-semibold transition ${
              tab === key ? "bg-brand-600 text-canvas" : "text-ink hover:bg-paper"
            }`}
          >
            {label} ·{" "}
            {/* No "0" while loading (it then jumped to the real number) */}
            <span className="inline-block min-w-[1ch] tabular-nums">
              {(key === "verified" ? books.data : list.data) ? count : "…"}
            </span>
          </button>
        ))}
      </div>

      {/* Under the tabs, so the tabs do not move when these appear after loading */}
      <SellerNotices />

      {actionError && (
        <div className="mb-4">
          <ErrorBox error={actionError} />
        </div>
      )}

      {tab === "verified" ? (
        <RedBookList />
      ) : (
        <>
          {list.isPending && <Spinner />}
          {list.isError && <ErrorBox error={list.error} onRetry={() => list.refetch()} />}
          {tab === "review" && inReview.length > 0 && (
            <p className="mb-4 rounded-2xl bg-paper px-4 py-3 text-sm text-muted">
              Chủ đầu tư thường duyệt trong 24 giờ. Nhập sai? Bấm <strong className="text-ink">“Sửa thông tin”</strong> để sửa
              ngay, tin vẫn giữ chỗ trong hàng chờ. Tin bị từ chối hiện lý do ngay trên tin: bấm{" "}
              <strong className="text-ink">“Sửa & gửi duyệt lại”</strong>.
            </p>
          )}
          {list.data && shown.length === 0 && (
            <p className="rounded-3xl bg-paper px-5 py-8 text-center text-muted">
              {tab === "review"
                ? "Không có tin nào đang chờ duyệt."
                : all.length === 0
                  ? "Bạn chưa đăng căn nào. Bấm “+ Đăng bán căn” để bắt đầu."
                  : "Chưa có căn nào được duyệt. Xem tab “Căn đang yêu cầu duyệt”."}
            </p>
          )}
          <ul className="space-y-4">
            {shown.map((p) => (
              <ListingCard
                key={p.id}
                property={p}
                stats={stats.get(p.id)}
                highlighted={p.id === target}
                busy={busy}
                onSubmit={() => submit.mutate(p.id)}
                onWithdraw={() => {
                  if (window.confirm("Tạm ngừng bán căn này? Căn sẽ không còn được gợi ý cho người mua.")) withdraw.mutate(p.id);
                }}
                onSold={() => {
                  sold.reset();
                  setSelling(p);
                }}
              />
            ))}
          </ul>
        </>
      )}
      {selling && (
        <ConfirmSold
          property={selling}
          busy={sold.isPending}
          error={sold.error}
          onConfirm={(buyerId) => sold.mutate({ id: selling.id, buyerId })}
          onCancel={() => setSelling(null)}
        />
      )}
    </div>
  );
}

/** One listing (design): photo, status, price, place and size, how buyers react, and what to do next. */
function ListingCard({
  property: p,
  stats,
  highlighted,
  busy,
  onSubmit,
  onWithdraw,
  onSold,
}: {
  property: Property;
  stats?: Stats;
  highlighted: boolean;
  busy: boolean;
  onSubmit: () => void;
  onWithdraw: () => void;
  onSold: () => void;
}) {
  const images = imagesOf(p);
  const [viewer, setViewer] = useState<number | null>(null);
  const rejected = p.status === "REJECTED";
  // Opened from a notification: the card lights up (and is scrolled to)
  const flash = useJumpFlash(highlighted);
  // Fixing the listing happens right here, under its card
  const [editing, setEditing] = useState(false);
  return (
    <li
      ref={(el) => {
        if (el && highlighted) el.scrollIntoView({ behavior: "smooth", block: "center" });
        flash(el);
      }}
      className={`rounded-[28px] bg-paper p-4 ${highlighted ? "ring-2 ring-brand-500" : ""} ${rejected ? "ring-2 ring-red-200" : ""}`}
    >
      <div className="flex flex-col gap-5 sm:flex-row">
        <button
          type="button"
          className="group relative block shrink-0 overflow-hidden rounded-3xl disabled:cursor-default"
          disabled={images.length === 0}
          onClick={() => setViewer(0)}
          aria-label={`Xem ${images.length} ảnh căn ${p.unit_code}`}
        >
          <PropertyImage
            src={images[0]?.url}
            alt={`Ảnh căn ${p.unit_code}`}
            className="h-44 w-full rounded-3xl transition duration-300 group-hover:scale-105 sm:h-40 sm:w-48"
          />
          {images.length > 0 && (
            <span className="absolute bottom-2 left-2 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-semibold text-white">
              ⤢ {images.length} ảnh
            </span>
          )}
        </button>
        {viewer !== null && (
          <PhotoViewer
            images={images}
            start={viewer}
            title={p.unit_code}
            info={<PropertyPhotoInfo property={p} />}
            onClose={() => setViewer(null)}
          />
        )}

        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-display text-2xl font-bold leading-tight">{p.unit_code}</h3>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_TONE[p.status]}`}>
                {PROPERTY_STATUS[p.status]}
              </span>
            </div>
            <p className="font-display text-2xl font-bold text-brand-700">{formatVnd(p.price_vnd)}</p>
          </div>
          <p className="text-muted">
            {p.building_name} · {p.project_name} · {formatArea(p.area_m2)} · {p.bedrooms === 0 ? "Studio" : `${p.bedrooms} PN`} · Tầng{" "}
            {p.floor}
          </p>

          {p.status === "AVAILABLE" && stats && (
            <dl className="flex flex-wrap gap-x-8 gap-y-2">
              <Stat value={stats.ai_suggestions} label="lần AI gợi ý" />
              <Stat value={stats.viewing_requests} label="yêu cầu xem" />
              <Stat value={stats.open_slots_week} label="khung giờ mở tuần này" />
            </dl>
          )}
          {p.status === "PENDING_REVIEW" && (
            <p className="text-sm">Chủ đầu tư đang duyệt tin, thường xong trong 24 giờ; bạn sẽ nhận thông báo khi có kết quả.</p>
          )}
          {rejected && (
            <div className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-900 ring-1 ring-red-200">
              <p className="font-bold">Chủ đầu tư chưa duyệt tin này</p>
              <p className="mt-0.5">
                <span className="font-semibold">Lý do:</span> {p.rejection_reason || "không ghi lý do"}
              </p>
              <p className="mt-1 text-xs text-red-800/80">Sửa theo lý do trên rồi bấm “Lưu & gửi duyệt lại”.</p>
            </div>
          )}

          <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
            {EDITABLE.has(p.status) && (
              <button
                type="button"
                onClick={() => setEditing((v) => !v)}
                aria-expanded={editing}
                className="rounded-full bg-brand-600 px-4 py-2 text-sm font-bold text-canvas hover:bg-brand-700"
              >
                {editing ? "Đóng chỉnh sửa" : rejected ? "Sửa & gửi duyệt lại" : "Sửa thông tin"}
              </button>
            )}
            {p.status !== "SOLD" && (
              <Link
                to={`/owner/properties/${p.id}/slots`}
                className="rounded-full border border-ink/15 px-4 py-2 text-sm font-bold hover:bg-sand"
              >
                Thay đổi khung giờ
              </Link>
            )}
            {p.status === "WITHDRAWN" && (
              <button
                type="button"
                disabled={busy}
                onClick={onSubmit}
                className="rounded-full bg-brand-600 px-4 py-2 text-sm font-bold text-canvas hover:bg-brand-700"
              >
                Mở bán lại
              </button>
            )}
            {p.status === "AVAILABLE" && (
              <>
                <button type="button" disabled={busy} onClick={onWithdraw} className="px-3 py-2 text-sm font-bold text-brand-700 hover:underline">
                  Tạm ngừng
                </button>
                <button type="button" disabled={busy} onClick={onSold} className="px-3 py-2 text-sm font-bold text-brand-700 hover:underline">
                  Đánh dấu đã bán
                </button>
                <p className="basis-full text-xs text-muted">
                  Muốn đổi giá, ảnh hay mô tả? Bấm “Tạm ngừng”, sửa thông tin rồi “Mở bán lại” để Chủ đầu tư duyệt lại.
                </p>
              </>
            )}
            {/* Sold while off the market or waiting for review: it can be closed for good too */}
            {(p.status === "WITHDRAWN" || p.status === "PENDING_REVIEW" || p.status === "REJECTED") && (
              <button type="button" disabled={busy} onClick={onSold} className="px-3 py-2 text-sm font-bold text-brand-700 hover:underline">
                Đánh dấu đã bán
              </button>
            )}
          </div>
        </div>
      </div>
      {editing && (
        <div className="mt-4 border-t border-line pt-4">
          <PropertyFormPage propertyId={p.id} onClose={() => setEditing(false)} />
        </div>
      )}
    </li>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <dd className="font-display text-xl font-bold leading-none">{value}</dd>
      <dt className="text-xs text-muted">{label}</dt>
    </div>
  );
}

/** Where the seller stands: profile review by the investor, and red books not listed yet. */
function SellerNotices() {
  const books = useRedBooks();
  const profile = useQuery({ queryKey: ["owner-verification"], queryFn: () => call(api.GET("/api/v1/owner/verification")) });
  if (!books.data || profile.isPending) return null;
  const usable = usableRedBooks(books.data).length;
  const status = profile.data?.verification_status;

  return (
    <div className="mb-5 space-y-2">
      {/* A verified red book verifies the seller; until then, say how */}
      {status && status !== "VERIFIED" && books.data.length > 0 && (
        <Notice tone="warning">
          Tài khoản người bán của bạn chưa được xác thực. Xác thực một sổ đỏ / sổ hồng (họ tên, mã số sổ và mã OTP) để hoàn tất.
        </Notice>
      )}
      {(books.data.length === 0 || usable > 0) && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl bg-leaf/70 px-5 py-4">
          <p>
            {books.data.length === 0 ? (
              "Bạn cần xác thực sổ đỏ / sổ hồng trước khi đăng bán."
            ) : (
              <>
                Bạn có <strong>{usable} sổ đỏ / sổ hồng đã xác thực</strong> chưa đăng bán.
              </>
            )}
          </p>
          <Link
            to={books.data.length === 0 ? "/owner/verify" : "/owner?tab=verified"}
            className="rounded-full border border-ink/20 bg-paper px-4 py-2 text-sm font-bold hover:bg-canvas"
          >
            {books.data.length === 0 ? "Xác thực sổ đỏ / sổ hồng" : "Xem sổ đỏ / sổ hồng"}
          </Link>
        </div>
      )}
    </div>
  );
}

/** Second confirmation before "Đã bán": spells out that it is final and needs an explicit "I understand". */
function ConfirmSold({
  property: p,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  property: Property;
  busy: boolean;
  error: unknown;
  onConfirm: (buyerId: number | null) => void;
  onCancel: () => void;
}) {
  const [understood, setUnderstood] = useState(false);
  // Who bought it: one of the buyers who viewed it here (they keep "Quan tâm", the others are told it was sold),
  // or someone outside BookingBot. undefined = not chosen yet
  const [buyer, setBuyer] = useState<number | null | undefined>(undefined);
  // The viewings still ahead of this home: marking it sold cancels them and tells those buyers it was sold
  const bookings = useQuery({
    queryKey: ["owner-bookings", "sold-check", p.id],
    queryFn: () => call(api.GET("/api/v1/owner/bookings")),
  });
  const now = Date.now();
  const ahead = (bookings.data ?? []).filter(
    (b) =>
      b.property_id === p.id &&
      (b.status === "REQUESTED" ||
        ((b.status === "CONFIRMED" || b.status === "RESCHEDULE_REQUESTED") && Date.parse(b.start_at) > now)),
  );
  const buyers = new Set(ahead.map((b) => b.customer_id)).size;
  // Buyers whose viewing of this home took place
  const viewers = [
    ...new Map(
      (bookings.data ?? [])
        .filter(
          (b) =>
            b.property_id === p.id &&
            (b.status === "COMPLETED" || (b.status === "CONFIRMED" && Date.parse(b.start_at) <= now)),
        )
        .map((b) => [b.customer_id, b.customer_name ?? b.buyer_ref]),
    ),
  ];
  const chosen = viewers.length === 0 ? null : buyer;
  return createPortal(
    <div
      className="theme-seller fixed inset-0 z-50 grid place-items-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sold-title"
      onClick={onCancel}
    >
      <div className="w-full max-w-md rounded-3xl bg-paper p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h2 id="sold-title" className="font-display text-2xl font-bold">
          Đánh dấu căn {p.unit_code} đã bán?
        </h2>
        <p className="mt-1 text-sm text-muted">
          {p.building_name} · {p.project_name} · {formatVnd(p.price_vnd)}
        </p>
        <div className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-900 ring-1 ring-red-200">
          <p className="font-bold">Thao tác này không hoàn tác được:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            <li>Tin đăng đóng hẳn, không mở bán lại được.</li>
            <li>Người mua không còn thấy căn và không đặt lịch xem được.</li>
            <li>Sổ đỏ / sổ hồng của căn không dùng để đăng bán lại được nữa.</li>
            {ahead.length > 0 && (
              <li className="font-semibold">
                {ahead.length} lịch xem sắp tới sẽ bị hủy và {buyers} người mua được báo là căn đã bán.
              </li>
            )}
          </ul>
          <p className="mt-2 text-xs">Chỉ muốn ngừng bán một thời gian? Dùng “Tạm ngừng” thay vì đánh dấu đã bán.</p>
        </div>
        {viewers.length > 0 && (
          <fieldset className="mt-4 space-y-1.5 text-sm">
            <legend className="mb-1 font-semibold">Bạn đã bán cho ai?</legend>
            {viewers.map(([id, name]) => (
              <label key={id} className="flex items-center gap-2">
                <input type="radio" name="sold-to" className="size-4" checked={buyer === id} onChange={() => setBuyer(id)} />
                {name} <span className="text-muted">(đã xem căn trên BookingBot)</span>
              </label>
            ))}
            <label className="flex items-center gap-2">
              <input type="radio" name="sold-to" className="size-4" checked={buyer === null} onChange={() => setBuyer(null)} />
              Người mua ngoài BookingBot
            </label>
            <p className="text-xs text-muted">Những người đã xem còn lại sẽ được báo là căn đã bán.</p>
          </fieldset>
        )}
        <label className="mt-4 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-red-600"
            checked={understood}
            onChange={(e) => setUnderstood(e.target.checked)}
          />
          Tôi hiểu căn {p.unit_code} đã bán thật và không thể đăng lại.
        </label>
        {error != null && (
          <div className="mt-3">
            <ErrorBox error={error} />
          </div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded-full px-5 py-2.5 text-sm font-bold hover:bg-sand" autoFocus>
            Hủy
          </button>
          <button
            type="button"
            disabled={!understood || busy || chosen === undefined}
            onClick={() => onConfirm(chosen ?? null)}
            className="rounded-full bg-red-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-40"
          >
            {busy ? "Đang lưu..." : "Xác nhận đã bán"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
