import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import type { Property } from "../../api/types";
import { ErrorBox, Notice, Spinner } from "../../components/ui";
import { formatArea, formatVnd, PROPERTY_STATUS } from "../../lib/format";
import { imagesOf, PropertyImage } from "../../buyer/shared";
import { usableRedBooks, useOwnerOverview, useOwnerProperties, useRedBooks } from "./ownerData";
import { RedBookList } from "./RedBooks";

type Tab = "listings" | "verified";
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
  const tab: Tab = params.get("tab") === "verified" && !target ? "verified" : "listings";

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
    mutationFn: (id: number) => call(api.POST("/api/v1/owner/properties/{property_id}/sold", path(id))),
    onSuccess: refresh,
  });
  const actionError = submit.error ?? withdraw.error ?? sold.error;
  const busy = submit.isPending || withdraw.isPending || sold.isPending;

  const stats = new Map<number, Stats>((overview.data?.properties ?? []).map((s) => [s.property_id, s]));
  const all = list.data ?? [];
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

      <SellerNotices />

      <div className="mb-5 flex w-fit rounded-full bg-sand p-1" role="tablist" aria-label="Căn của tôi">
        {(
          [
            ["listings", "Căn đăng bán", all.length],
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
            {label} · {count}
          </button>
        ))}
      </div>

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
          {list.data?.length === 0 && (
            <p className="rounded-3xl bg-paper px-5 py-8 text-center text-muted">
              Bạn chưa đăng căn nào. Bấm “+ Đăng bán căn” để bắt đầu.
            </p>
          )}
          <ul className="space-y-4">
            {all.map((p) => (
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
                  if (window.confirm("Đánh dấu căn này đã bán?")) sold.mutate(p.id);
                }}
              />
            ))}
          </ul>
        </>
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
  return (
    <li
      ref={(el) => {
        if (el && highlighted) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }}
      className={`flex flex-col gap-5 rounded-[28px] bg-paper p-4 sm:flex-row ${highlighted ? "ring-2 ring-brand-500" : ""}`}
    >
      <div className="relative shrink-0">
        <PropertyImage src={images[0]?.url} alt={`Ảnh căn ${p.unit_code}`} className="h-44 w-full rounded-3xl sm:h-40 sm:w-48" />
        {images.length > 0 && (
          <span className="absolute bottom-2 left-2 rounded-full bg-black/50 px-2 py-0.5 text-[11px] font-semibold text-white">
            {images.length} ảnh
          </span>
        )}
      </div>

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
        {p.status === "REJECTED" && p.rejection_reason && (
          <p className="rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-800">Lý do từ chối: {p.rejection_reason}</p>
        )}

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
          {p.status !== "SOLD" && (
            <Link
              to={`/owner/properties/${p.id}/slots`}
              className="rounded-full border border-ink/15 px-4 py-2 text-sm font-bold hover:bg-sand"
            >
              Thay đổi khung giờ
            </Link>
          )}
          {(p.status === "DRAFT" || p.status === "REJECTED" || p.status === "WITHDRAWN") && (
            <button
              type="button"
              disabled={busy}
              onClick={onSubmit}
              className="rounded-full bg-brand-600 px-4 py-2 text-sm font-bold text-canvas hover:bg-brand-700"
            >
              {p.status === "WITHDRAWN" ? "Mở bán lại" : "Gửi duyệt"}
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
            </>
          )}
        </div>
      </div>
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
  if (!books.data) return null;
  const usable = usableRedBooks(books.data).length;
  const status = profile.data?.verification_status;

  return (
    <div className="mb-5 space-y-2">
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
      {(books.data.length === 0 || usable > 0) && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl bg-leaf/70 px-5 py-4">
          <p>
            {books.data.length === 0 ? (
              "Bạn cần xác thực sổ đỏ trước khi đăng bán."
            ) : (
              <>
                Bạn có <strong>{usable} sổ đỏ đã xác thực</strong> chưa đăng bán.
              </>
            )}
          </p>
          <Link
            to={books.data.length === 0 ? "/owner/verify" : "/owner?tab=verified"}
            className="rounded-full border border-ink/20 bg-paper px-4 py-2 text-sm font-bold hover:bg-canvas"
          >
            {books.data.length === 0 ? "Xác thực sổ đỏ" : "Xem sổ đỏ"}
          </Link>
        </div>
      )}
    </div>
  );
}
