import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { api, call } from "../../api/client";
import type { Direction, Furnishing, LegalStatus, Property, PropertyCreate, PropertyType, ViewType } from "../../api/types";
import { MediaManager } from "../../components/MediaManager";
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
  };
}

/** Create (/owner/properties/new) or edit (/owner/properties/:id/edit) a listing. */
export function PropertyFormPage() {
  const params = useParams();
  const editingId = params.id ? Number(params.id) : null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<FormState>(() => ({ ...EMPTY, verification_id: searchParams.get("verification") ?? "" }));
  const redBooks = useRedBooks();
  const usable = usableRedBooks(redBooks.data);

  const projects = useQuery({ queryKey: ["projects"], queryFn: () => call(api.GET("/api/v1/projects")) });
  const existing = useQuery({
    queryKey: ["property", editingId],
    enabled: editingId !== null,
    queryFn: () => call(api.GET("/api/v1/properties/{property_id}", { params: { path: { property_id: editingId! } } })),
  });

  useEffect(() => {
    if (existing.data) setForm(fromProperty(existing.data));
  }, [existing.data]);

  // Drop a preselected red book (?verification=) that is not usable, e.g. already backing a listing
  useEffect(() => {
    if (redBooks.data && !usable.some((b) => String(b.id) === form.verification_id)) {
      setForm((f) => (f.verification_id ? { ...f, verification_id: "" } : f));
    }
  }, [redBooks.data, usable, form.verification_id]);

  const save = useMutation({
    mutationFn: (payload: PropertyCreate) => {
      if (editingId === null) return call(api.POST("/api/v1/owner/properties", { body: payload }));
      const { building_id: _building, verification_id: _redBook, ...changes } = payload;
      return call(api.PATCH("/api/v1/owner/properties/{property_id}", { params: { path: { property_id: editingId } }, body: changes }));
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["owner-properties"] });
      queryClient.invalidateQueries({ queryKey: ["property", editingId] });
      // A new draft continues on its edit page so the owner can add photos and the ownership document
      navigate(editingId === null ? `/owner/properties/${saved.id}/edit` : "/owner");
    },
  });

  if (editingId !== null && existing.isPending) return <Spinner />;
  if (existing.isError) return <ErrorBox error={existing.error} />;
  // A new listing must be backed by a verified red book the seller has not used yet
  const needsRedBook = editingId === null && redBooks.isSuccess && usable.length === 0;
  const locked = needsRedBook || (existing.data !== undefined && !["DRAFT", "REJECTED", "WITHDRAWN"].includes(existing.data.status));

  const buildings = projects.data?.find((p) => p.code === form.projectCode)?.buildings ?? [];
  const set =
    <K extends keyof FormState>(key: K) =>
    (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [key]: e.target.value as FormState[K] }));

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate(toPayload(form));
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/owner" className="text-sm text-muted hover:text-ink">
        ← Căn của tôi
      </Link>
      <PageHeader
        title={editingId === null ? "Đăng căn mới" : "Sửa tin đăng"}
        subtitle="Tin được lưu dưới dạng bản nháp. Thêm ảnh rồi bấm “Gửi duyệt” để Chủ đầu tư kiểm duyệt."
      />
      {needsRedBook && (
        <Notice tone="warning">
          Bạn cần xác thực sổ đỏ của căn trước khi đăng bán.{" "}
          <Link to="/owner/verify" className="font-medium underline">
            Xác thực sổ đỏ
          </Link>
        </Notice>
      )}
      {locked && !needsRedBook && <Notice tone="warning">Tin đã gửi duyệt hoặc đang bán nên không thể sửa.</Notice>}

      <form onSubmit={onSubmit} className="card mt-4 space-y-5 p-5">
        {save.isError && <ErrorBox error={save.error} />}

        <fieldset disabled={locked} className="space-y-5">
          {editingId === null && usable.length > 0 && (
            <Field label="Sổ đỏ đã xác thực" id="red-book">
              <select id="red-book" className="input" required value={form.verification_id} onChange={set("verification_id")}>
                <option value="">Chọn sổ đỏ của căn</option>
                {usable.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.red_book_code} · {b.red_book_holder_name}
                  </option>
                ))}
              </select>
            </Field>
          )}
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
            <Field label="Giá bán (tỷ VNĐ)" id="price">
              <input id="price" className="input" required inputMode="decimal" placeholder="3,2" value={form.price_ty} onChange={set("price_ty")} />
            </Field>
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
            <Field label="View" id="view">
              <Select id="view" value={form.view} onChange={set("view")} options={VIEW} />
            </Field>
            <Field label="Nội thất" id="furnishing">
              <Select id="furnishing" value={form.furnishing} onChange={set("furnishing")} options={FURNISHING} />
            </Field>
            <Field label="Pháp lý" id="legal">
              <Select id="legal" value={form.legal_status} onChange={set("legal_status")} options={LEGAL} />
            </Field>
          </div>

          <Field label="Mô tả" id="desc">
            <textarea id="desc" rows={4} maxLength={5000} className="input" value={form.description} onChange={set("description")} />
          </Field>
        </fieldset>

        <div className="flex justify-end gap-2">
          <Link to="/owner" className="btn-secondary">
            Hủy
          </Link>
          <button type="submit" className="btn-primary" disabled={locked || save.isPending}>
            {save.isPending ? "Đang lưu..." : "Lưu bản nháp"}
          </button>
        </div>
      </form>

      {existing.data && (
        <div className="mt-6">
          <MediaManager property={existing.data} editable={!locked} />
        </div>
      )}
    </div>
  );
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
