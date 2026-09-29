import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

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

const CONTENT_TYPE: Record<Kind, string> = {
  IMAGE: "image/jpeg",
  VIDEO: "video/mp4",
  FLOORPLAN: "image/png",
  OWNERSHIP_DOC: "application/pdf",
};

/**
 * Photos / floor plans / ownership document of a listing (spec §4.5).
 * Files are uploaded to S3 separately; here the owner registers the S3 key or URL.
 * Ownership documents are always private: only the owner and the investor see them.
 */
export function MediaManager({ property, editable }: { property: Property; editable: boolean }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<Kind>("OWNERSHIP_DOC");
  const [key, setKey] = useState("");
  const media = property.media ?? [];
  const hasDoc = media.some((m) => m.kind === "OWNERSHIP_DOC");
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["property", property.id] });
    queryClient.invalidateQueries({ queryKey: ["owner-properties"] });
  };

  const add = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/owner/properties/{property_id}/media", {
          params: { path: { property_id: property.id } },
          body: { kind, s3_key: key.trim(), content_type: CONTENT_TYPE[kind], sort_order: media.length, is_public: kind !== "OWNERSHIP_DOC" },
        }),
      ),
    onSuccess: () => {
      setKey("");
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

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  return (
    <section className="card space-y-4 p-5" aria-labelledby="media-title">
      <h2 id="media-title" className="font-semibold">
        Ảnh & giấy tờ
      </h2>
      {!hasDoc && (
        <Notice tone="warning">Cần ít nhất một giấy tờ sở hữu để gửi duyệt — Chủ đầu tư dùng giấy tờ này để xác minh căn.</Notice>
      )}
      {(add.error ?? remove.error) && <ErrorBox error={add.error ?? remove.error} />}

      {media.length > 0 && (
        <ul className="divide-y divide-line text-sm">
          {media.map((m) => (
            <li key={m.id} className="flex items-center gap-3 py-2">
              <span className="w-40 shrink-0 text-muted">{KIND[m.kind]}</span>
              <a href={m.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate font-mono text-xs text-brand-700 hover:underline">
                {m.url}
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
        <form onSubmit={onSubmit} className="grid gap-2 sm:grid-cols-[auto_1fr_auto]">
          <label htmlFor="media-kind" className="sr-only">
            Loại
          </label>
          <select id="media-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            {(Object.entries(KIND) as [Kind, string][]).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
          <label htmlFor="media-key" className="sr-only">
            Đường dẫn S3 hoặc URL
          </label>
          <input
            id="media-key"
            className="input font-mono text-xs"
            required
            minLength={3}
            placeholder="S3 key hoặc URL, VD: private/units/S2-1208/so-hong.pdf"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          <button type="submit" className="btn-secondary" disabled={add.isPending}>
            Thêm
          </button>
        </form>
      ) : (
        <p className="text-xs text-muted">Tin đang được duyệt hoặc đang bán nên không thể thay đổi ảnh/giấy tờ.</p>
      )}
    </section>
  );
}
