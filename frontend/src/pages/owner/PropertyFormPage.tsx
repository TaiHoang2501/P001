import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import type { Direction, Furnishing, LegalStatus, Property, PropertyCreate, PropertyType, ViewType } from "../../api/types";
import { imagesOf } from "../../buyer/shared";
import { PhotoPicker, type Photo } from "../../components/PhotoPicker";
import { ErrorBox, Notice, PageHeader, Spinner } from "../../components/ui";
import { DIRECTION, FURNISHING, LEGAL, PROPERTY_TYPE, VIEW } from "../../lib/format";
import { usableRedBooks, useRedBooks } from "./ownerData";

interface FormState {
  verification_id: string;
  projectCode: string;
  building_id: string;
  unit_code: string;
  property_type: PropertyType;
  bedrooms: string;
  bathrooms: string;
  area_m2: string;
  floor: string;
  price_ty: string;
  direction: Direction;
  view: ViewType;
  furnishing: Furnishing;
  legal_status: LegalStatus;
  description: string;
}

const EMPTY: FormState = {
  verification_id: "",
  projectCode: "",
  building_id: "",
  unit_code: "",
  property_type: "APARTMENT",
  bedrooms: "2",
  bathrooms: "2",
  area_m2: "",
  floor: "",
  price_ty: "",
  direction: "SE",
  view: "INTERNAL",
  furnishing: "BASIC",
  legal_status: "PINK_BOOK",
  description: "",
};

function fromProperty(p: Property): FormState {
  return {
    // Only needed when creating; an existing listing keeps its red book
    verification_id: "",
    projectCode: p.project_code,
    building_id: String(p.building_id),
    unit_code: p.unit_code,
    property_type: p.property_type,
    bedrooms: String(p.bedrooms),
    bathrooms: String(p.bathrooms),
    area_m2: String(p.area_m2),
    floor: String(p.floor),
    price_ty: String(p.price_vnd / 1_000_000_000),
    direction: p.direction,
    view: p.view,
    furnishing: p.furnishing,
    legal_status: p.legal_status,
    description: p.description,
  };
}

function toPayload(f: FormState): PropertyCreate {
  return {
    verification_id: Number(f.verification_id),
    building_id: Number(f.building_id),
    unit_code: f.unit_code.trim(),
    property_type: f.property_type,
    bedrooms: Number(f.bedrooms),
    bathrooms: Number(f.bathrooms),
    area_m2: f.area_m2.replace(",", "."),
    floor: Number(f.floor),
    price_vnd: Math.round(parseFloat(f.price_ty.replace(",", ".")) * 1_000_000_000),
    direction: f.direction,
    view: f.view,
    furnishing: f.furnishing,
    legal_status: f.legal_status,
    description: f.description.trim(),
    photos: [],
  };
}

// Statuses in which the seller may still change the listing (a listing waiting for review included)
const EDITABLE = ["DRAFT", "PENDING_REVIEW", "REJECTED", "WITHDRAWN"];
// Saving these sends the listing (back) to the investor for review
const SEND_ON_SAVE = ["DRAFT", "REJECTED"];

/** Create (/owner/properties/new, "Đăng tin bán") or edit (/owner/properties/:id/edit) a listing. */
export function PropertyFormPage({
  propertyId,
  onClose,
}: {
  /** Inline editor (inside the listing's card on "Căn đang yêu cầu duyệt") instead of the page from the URL */
  propertyId?: number;
  onClose?: () => void;
} = {}) {
  const params = useParams();
  const inline = propertyId !== undefined;
  const editingId = propertyId ?? (params.id ? Number(params.id) : null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<FormState>(() => ({ ...EMPTY, verification_id: searchParams.get("verification") ?? "" }));
  const [photos, setPhotos] = useState<Photo[]>([]);
  const redBooks = useRedBooks();
  const usable = usableRedBooks(redBooks.data);

  const projects = useQuery({ queryKey: ["projects"], queryFn: () => call(api.GET("/api/v1/projects")) });
  const existing = useQuery({
    queryKey: ["property", editingId],
    enabled: editingId !== null,
    queryFn: () => call(api.GET("/api/v1/properties/{property_id}", { params: { path: { property_id: editingId! } } })),
  });

  useEffect(() => {
    if (!existing.data) return;
    setForm(fromProperty(existing.data));
    setPhotos(
      imagesOf(existing.data)
        .filter((m) => m.kind === "IMAGE")
        .map((m) => ({ key: m.url, url: m.url, mediaId: m.id })),
    );
  }, [existing.data]);

  // The home on the chosen red book (investor's data): fills the facts the seller cannot change
  const book = editingId === null ? usable.find((b) => String(b.id) === form.verification_id) : undefined;
  const unit = book?.unit ?? null;
  useEffect(() => {
    if (!unit) return;
    setForm((f) => ({
      ...f,
      projectCode: unit.project_code,
      building_id: String(unit.building_id),
      unit_code: unit.unit_code,
      property_type: unit.property_type,
      bedrooms: String(unit.bedrooms),
      bathrooms: String(unit.bathrooms),
      area_m2: String(unit.area_m2),
      floor: String(unit.floor),
      direction: unit.direction,
      legal_status: "PINK_BOOK",
    }));
  }, [unit]);

  // Drop a preselected red book (?verification=) that is not usable, e.g. already backing a listing
  useEffect(() => {
    if (redBooks.data && !usable.some((b) => String(b.id) === form.verification_id)) {
      setForm((f) => (f.verification_id ? { ...f, verification_id: "" } : f));
    }
  }, [redBooks.data, usable, form.verification_id]);

  const save = useMutation({
    mutationFn: async (payload: PropertyCreate): Promise<Property> => {
      // "Đăng tin bán": the listing, its photos and the request for review in one step
      if (editingId === null)
        return call(
          api.POST("/api/v1/owner/properties", { body: { ...payload, photos: photos.map((p) => p.key) } }),
        );
      const path = { params: { path: { property_id: editingId } } };
      const { building_id: _building, verification_id: _redBook, photos: _p, ...changes } = payload;
      let saved = await call(api.PATCH("/api/v1/owner/properties/{property_id}", { ...path, body: changes }));
      // Photos: drop the removed ones, attach the new uploads
      const kept = new Set(photos.map((p) => p.mediaId).filter(Boolean));
      for (const m of imagesOf(existing.data!).filter((m) => m.kind === "IMAGE" && !kept.has(m.id)))
        saved = await call(
          api.DELETE("/api/v1/owner/properties/{property_id}/media/{media_id}", {
            params: { path: { property_id: editingId, media_id: m.id } },
          }),
        );
      for (const [i, p] of photos.entries())
        if (!p.mediaId)
          saved = await call(
            api.POST("/api/v1/owner/properties/{property_id}/media", {
              ...path,
              body: { kind: "IMAGE", s3_key: p.key, content_type: "image/jpeg", sort_order: i, is_public: true },
            }),
          );
      if (SEND_ON_SAVE.includes(saved.status))
        saved = await call(api.POST("/api/v1/owner/properties/{property_id}/submit", path));
      return saved;
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["owner-properties"] });
      queryClient.invalidateQueries({ queryKey: ["property", editingId] });
      // The red book now backs a listing
      queryClient.invalidateQueries({ queryKey: ["owner-ownership"] });
      // Listings waiting for review (or rejected) are on the "Căn đang yêu cầu duyệt" tab
      queryClient.invalidateQueries({ queryKey: ["owner-overview"] });
      if (inline) onClose?.();
      else navigate(saved.status === "WITHDRAWN" ? `/owner?property=${saved.id}` : `/owner?tab=review&property=${saved.id}`);
    },
  });

  // Every hook before the early returns below (React needs the same hooks on every render)
  const [showPriceError, setShowPriceError] = useState(false);

  if (editingId !== null && existing.isPending) return <Spinner />;
  if (existing.isError) return <ErrorBox error={existing.error} />;
  // A new listing must be backed by a verified red book the seller has not used yet
  const needsRedBook = editingId === null && redBooks.isSuccess && usable.length === 0;
  const status = existing.data?.status;
  const locked = needsRedBook || (status !== undefined && !EDITABLE.includes(status));
  const needsPhoto = editingId === null && photos.length === 0;
  // Facts from the red book are shown, not typed (an older red book without them falls back to the inputs)
  const fromBook = editingId === null ? unit !== null : existing.data?.verified_red_book === true;
  const project = projects.data?.find((p) => p.code === form.projectCode);
  const facts: [string, string][] = [
    ["Dự án", unit?.project_name ?? existing.data?.project_name ?? project?.name ?? ""],
    ["Tòa", unit?.building_name ?? existing.data?.building_name ?? ""],
    ["Mã căn", form.unit_code],
    ["Loại hình", PROPERTY_TYPE[form.property_type]],
    ["Diện tích", `${form.area_m2.replace(".", ",")} m²`],
    ["Phòng ngủ", form.bedrooms === "0" ? "Studio" : `${form.bedrooms} PN`],
    ["Phòng tắm", `${form.bathrooms} WC`],
    ["Tầng", form.floor],
    ["Hướng", DIRECTION[form.direction]],
    ["Pháp lý", LEGAL[form.legal_status]],
  ];

  const buildings = projects.data?.find((p) => p.code === form.projectCode)?.buildings ?? [];
  const set =
    <K extends keyof FormState>(key: K) =>
    (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [key]: e.target.value as FormState[K] }));

  const priceError = priceProblem(form.price_ty);
  const perM2 = pricePerM2(form.price_ty, form.area_m2);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (priceError) {
      setShowPriceError(true);
      return;
    }
    save.mutate(toPayload(form));
  }

  return (
    <div className={inline ? "" : "mx-auto max-w-3xl"}>
      {!inline && (
        <>
        <Link to="/owner" className="text-sm text-muted hover:text-ink">
          ← Căn của tôi
        </Link>
        <PageHeader
          title={editingId === null ? "Đăng căn mới" : "Sửa tin đăng"}
          subtitle={
            editingId === null
              ? "Điền thông tin, thêm ảnh rồi bấm “Đăng tin bán”: tin được gửi Chủ đầu tư duyệt. Trong lúc chờ duyệt bạn vẫn sửa được."
              : status === "PENDING_REVIEW"
                ? "Tin đang chờ Chủ đầu tư duyệt. Sửa chỗ nhập sai rồi bấm “Lưu thay đổi”; tin vẫn ở hàng chờ duyệt."
                : "Sửa thông tin và ảnh của căn."
          }
        />
        </>
      )}
      {!inline && status === "REJECTED" && existing.data?.rejection_reason && (
        <Notice tone="warning">Chủ đầu tư chưa duyệt tin: {existing.data.rejection_reason}. Sửa lại rồi gửi duyệt lại.</Notice>
      )}
      {needsRedBook && (
        <Notice tone="warning">
          Bạn cần xác thực sổ đỏ / sổ hồng của căn trước khi đăng bán.{" "}
          <Link to="/owner/verify" className="font-medium underline">
            Xác thực sổ đỏ / sổ hồng
          </Link>
        </Notice>
      )}
      {locked && !needsRedBook && <Notice tone="warning">Tin đang bán hoặc đã bán nên không thể sửa.</Notice>}

      <form onSubmit={onSubmit} className={inline ? "space-y-5" : "card mt-4 space-y-5 p-5"}>
        {save.isError && <ErrorBox error={save.error} />}

        <fieldset disabled={locked} className="space-y-5">
          {editingId === null && usable.length > 0 && (
            <Field label="Sổ đỏ / sổ hồng đã xác thực" id="red-book">
              <select id="red-book" className="input" required value={form.verification_id} onChange={set("verification_id")}>
                <option value="">Chọn sổ đỏ / sổ hồng của căn</option>
                {usable.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.red_book_code} · {b.red_book_holder_name}
                    {b.unit ? ` · căn ${b.unit.unit_code} (${String(b.unit.area_m2).replace(".", ",")} m²)` : ""}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {fromBook ? (
            <section className="rounded-2xl bg-leaf/60 p-4" aria-label="Thông tin căn theo sổ đỏ / sổ hồng">
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-leaf-ink">
                ✓ Thông tin căn theo sổ đỏ / sổ hồng{book ? ` ${book.red_book_code}` : existing.data?.red_book_code ? ` ${existing.data.red_book_code}` : ""}
                <span className="font-normal text-muted">· dữ liệu của Chủ đầu tư, không cần nhập và không sửa được</span>
              </p>
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-5">
                {facts.map(([label, value]) => (
                  <div key={label} className="min-w-0">
                    <dt className="text-xs text-muted">{label}</dt>
                    <dd className="font-semibold leading-snug">{value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : (
            editingId === null &&
            !book && (
              <p className="rounded-2xl bg-paper px-4 py-3 text-sm text-muted">
                Chọn sổ đỏ / sổ hồng ở trên: thông tin căn (dự án, tòa, diện tích, số phòng, hướng…) sẽ được điền theo dữ liệu
                của Chủ đầu tư.
              </p>
            )
          )}

          {!fromBook && (editingId !== null || book) && (
            <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Dự án" id="project">
              <select
                id="project"
                className="input"
                required
                disabled={editingId !== null}
                value={form.projectCode}
                onChange={(e) => setForm((f) => ({ ...f, projectCode: e.target.value, building_id: "" }))}
              >
                <option value="">Chọn dự án</option>
                {projects.data?.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tòa" id="building">
              <select id="building" className="input" required disabled={editingId !== null || !form.projectCode} value={form.building_id} onChange={set("building_id")}>
                <option value="">Chọn tòa</option>
                {buildings.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Mã căn" id="unit">
              <input id="unit" className="input" required maxLength={50} placeholder="S2.01-1208" value={form.unit_code} onChange={set("unit_code")} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-4">
            <Field label="Diện tích (m²)" id="area">
              <input id="area" className="input" required inputMode="decimal" placeholder="68,5" value={form.area_m2} onChange={set("area_m2")} />
            </Field>
            <Field label="Tầng" id="floor">
              <input id="floor" type="number" className="input" required min={-5} max={200} value={form.floor} onChange={set("floor")} />
            </Field>
            <Field label="Loại hình" id="ptype">
              <Select id="ptype" value={form.property_type} onChange={set("property_type")} options={PROPERTY_TYPE} />
            </Field>
            <Field label="Phòng ngủ" id="beds">
              <input id="beds" type="number" className="input" required min={0} max={20} value={form.bedrooms} onChange={set("bedrooms")} />
            </Field>
            <Field label="Phòng tắm" id="baths">
              <input id="baths" type="number" className="input" required min={0} max={20} value={form.bathrooms} onChange={set("bathrooms")} />
            </Field>
            <Field label="Hướng" id="direction">
              <Select id="direction" value={form.direction} onChange={set("direction")} options={DIRECTION} />
            </Field>
            <Field label="Pháp lý" id="legal">
              <Select id="legal" value={form.legal_status} onChange={set("legal_status")} options={LEGAL} />
            </Field>
          </div>

            </>
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Giá bán (tỷ VNĐ)" id="price">
              <input
                id="price"
                className="input"
                inputMode="decimal"
                placeholder="3,2"
                aria-invalid={showPriceError && priceError !== null}
                aria-describedby="price-note"
                value={form.price_ty}
                // Digits and one decimal comma only (no minus sign, no letters)
                onChange={(e) => {
                  setShowPriceError(false);
                  setForm((f) => ({ ...f, price_ty: e.target.value.replace(/[^\d,.]/g, "") }));
                }}
                onBlur={() => setShowPriceError(form.price_ty.trim() !== "")}
              />
              <p id="price-note" className={`mt-1 text-xs ${showPriceError && priceError ? "font-medium text-red-700" : "text-muted"}`}>
                {showPriceError && priceError ? priceError : perM2 ? `≈ ${perM2} triệu/m²` : "Ví dụ 3,2 = 3,2 tỷ"}
              </p>
            </Field>
            <Field label="View" id="view">
              <Select id="view" value={form.view} onChange={set("view")} options={VIEW} />
            </Field>
            <Field label="Nội thất" id="furnishing">
              <Select id="furnishing" value={form.furnishing} onChange={set("furnishing")} options={FURNISHING} />
            </Field>
          </div>

          <Field label="Mô tả" id="desc">
            <textarea id="desc" rows={4} maxLength={5000} className="input" value={form.description} onChange={set("description")} />
          </Field>
        </fieldset>

        <PhotoPicker photos={photos} onChange={setPhotos} disabled={locked} />

        <div className="flex flex-wrap items-center justify-end gap-2">
          {needsPhoto && !locked && <p className="mr-auto text-sm text-muted">Thêm ít nhất 1 ảnh để đăng tin.</p>}
          {inline ? (
            <button type="button" className="btn-secondary" onClick={onClose}>
              Hủy
            </button>
          ) : (
            <Link to={editingId === null ? "/owner" : "/owner?tab=review"} className="btn-secondary">
              Hủy
            </Link>
          )}
          <button type="submit" className="btn-primary" disabled={locked || needsPhoto || save.isPending}>
            {save.isPending
              ? "Đang lưu..."
              : editingId === null
                ? "Đăng tin bán"
                : status && SEND_ON_SAVE.includes(status)
                  ? "Lưu & gửi duyệt lại"
                  : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </div>
  );
}

/** What is wrong with the price typed (in tỷ), or null when it is a sensible price. */
function priceProblem(raw: string): string | null {
  const text = raw.trim();
  if (!text) return "Nhập giá bán, ví dụ 3,2 (tỷ).";
  if (!/^\d+([.,]\d+)?$/.test(text)) return "Giá chỉ gồm số và một dấu phẩy thập phân, ví dụ 3,2.";
  const ty = parseFloat(text.replace(",", "."));
  if (ty < 0.1 || ty > 1000) return "Giá phải từ 0,1 đến 1.000 tỷ.";
  return null;
}

/** "≈ 52,6" (million VND per m²) once both the price and the area are known. */
function pricePerM2(priceTy: string, area: string): string | null {
  const ty = parseFloat(priceTy.replace(",", "."));
  const m2 = parseFloat(area.replace(",", "."));
  if (!(ty > 0) || !(m2 > 0) || priceProblem(priceTy)) return null;
  return ((ty * 1000) / m2).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      {children}
    </div>
  );
}

function Select<T extends string>({
  id,
  value,
  onChange,
  options,
}: {
  id: string;
  value: T;
  onChange: (e: { target: { value: string } }) => void;
  options: Record<T, string>;
}) {
  return (
    <select id={id} className="input" value={value} onChange={onChange}>
      {(Object.entries(options) as [T, string][]).map(([k, label]) => (
        <option key={k} value={k}>
          {label}
        </option>
      ))}
    </select>
  );
}
