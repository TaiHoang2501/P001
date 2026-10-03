import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";

import { api, call } from "../api/client";
import type { Media, Property } from "../api/types";
import { ErrorBox, Notice } from "./ui";

type Kind = Media["kind"];

const KIND: Record<Kind, string> = {
  IMAGE: "Ảnh",
  VIDEO: "Video",
  FLOORPLAN: "Mặt bằng",
  OWNERSHIP_DOC: "Giấy tờ sở hữu (sổ hồng/HĐMB)",
};

// Must match the backend's allowed types and size limits (property_service._UPLOAD_TYPES / _MAX_UPLOAD_MB)
const ACCEPT: Record<Kind, string> = {
  IMAGE: "image/jpeg,image/png,image/webp",
  VIDEO: "video/mp4,video/webm",
  FLOORPLAN: "image/jpeg,image/png,image/webp,application/pdf",
  OWNERSHIP_DOC: "application/pdf,image/jpeg,image/png",
};
const MAX_MB: Record<Kind, number> = { IMAGE: 10, VIDEO: 50, FLOORPLAN: 10, OWNERSHIP_DOC: 10 };

/**
 * Photos / floor plans / ownership document of a listing (spec §4.5).
 * Files are uploaded to object storage through the backend.
 * Ownership documents are always private: only the owner and the investor see them, through short-lived links.
 */
export function MediaManager({ property, editable }: { property: Property; editable: boolean }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<Kind>("IMAGE");
  const [file, setFile] = useState<File | null>(null);
  const [sizeError, setSizeError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const media = property.media ?? [];
  const hasDoc = media.some((m) => m.kind === "OWNERSHIP_DOC");
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["property", property.id] });
    queryClient.invalidateQueries({ queryKey: ["owner-properties"] });
  };

  const upload = useMutation({
    mutationFn: (f: File) =>
      call(
        api.POST("/api/v1/owner/properties/{property_id}/media/upload", {
          params: { path: { property_id: property.id } },
          body: { kind, file: f as unknown as string },
          bodySerializer: () => {
            const form = new FormData();
            form.append("kind", kind);
            form.append("file", f);
            return form;
          },
        }),
      ),
    onSuccess: () => {
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (mediaId: number) =>
      call(
        api.DELETE("/api/v1/owner/properties/{property_id}/media/{media_id}", {
          params: { path: { property_id: property.id, media_id: mediaId } },
        }),
      ),
    onSuccess: refresh,
  });

  function onFileChange(f: File | null) {
    upload.reset();
    if (f && f.size > MAX_MB[kind] * 1024 * 1024) {
      setSizeError(`Tệp quá lớn: tối đa ${MAX_MB[kind]} MB.`);
      setFile(null);
      return;
    }
    setSizeError(null);
    setFile(f);
  }

  function onKindChange(k: Kind) {
    setKind(k);
    setFile(null);
    setSizeError(null);
    if (fileInput.current) fileInput.current.value = "";
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (file) upload.mutate(file);
  }

  return (
    <section className="card space-y-4 p-5" aria-labelledby="media-title">
      <h2 id="media-title" className="font-semibold">
        Ảnh & giấy tờ
      </h2>
      {!hasDoc && (
        <Notice tone="warning">Cần ít nhất một giấy tờ sở hữu để gửi duyệt — Chủ đầu tư dùng giấy tờ này để xác minh căn.</Notice>
      )}
      {(upload.error ?? remove.error) && <ErrorBox error={upload.error ?? remove.error} />}

      {media.length > 0 && (
        <ul className="divide-y divide-line text-sm">
          {media.map((m) => (
            <li key={m.id} className="flex items-center gap-3 py-2">
              {m.content_type.startsWith("image/") ? (
                <img src={m.url} alt={KIND[m.kind]} loading="lazy" className="size-12 shrink-0 rounded-md bg-stone-100 object-cover" />
              ) : (
                <span className="flex size-12 shrink-0 items-center justify-center rounded-md bg-stone-100 text-[11px] uppercase text-stone-500">
                  {m.content_type.split("/")[1]}
                </span>
              )}
              <span className="w-32 shrink-0 text-muted sm:w-40">{KIND[m.kind]}</span>
              <a href={m.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-xs text-brand-700 hover:underline">
                Mở tệp
              </a>
              {!m.is_public && <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[11px] text-stone-600">Riêng tư</span>}
              {editable && (
                <button type="button" className="btn-danger btn-sm" disabled={remove.isPending} onClick={() => remove.mutate(m.id)}>
                  Xóa
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {editable ? (
        <form onSubmit={onSubmit} className="space-y-2">
          <div className="grid gap-2 sm:grid-cols-[auto_1fr_auto]">
            <label htmlFor="media-kind" className="sr-only">
              Loại
            </label>
            <select id="media-kind" className="input" value={kind} onChange={(e) => onKindChange(e.target.value as Kind)}>
              {(Object.entries(KIND) as [Kind, string][]).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
            <label htmlFor="media-file" className="sr-only">
              Chọn tệp
            </label>
            <input
              id="media-file"
              ref={fileInput}
              type="file"
              className="input text-xs"
              required
              accept={ACCEPT[kind]}
              onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
            />
            <button type="submit" className="btn-secondary" disabled={!file || upload.isPending}>
              {upload.isPending ? "Đang tải lên..." : "Tải lên"}
            </button>
          </div>
          {sizeError ? (
            <p className="text-xs text-red-700">{sizeError}</p>
          ) : (
            <p className="text-xs text-muted">
              Tối đa {MAX_MB[kind]} MB.
              {kind === "OWNERSHIP_DOC" && " Giấy tờ được lưu riêng tư, chỉ bạn và Chủ đầu tư xem được."}
            </p>
          )}
        </form>
      ) : (
        <p className="text-xs text-muted">Tin đang được duyệt hoặc đang bán nên không thể thay đổi ảnh/giấy tờ.</p>
      )}
    </section>
  );
}
