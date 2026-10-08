import { useRef, useState, type DragEvent } from "react";

import { api, call, errorMessage } from "../api/client";

/** A photo of the listing: just uploaded (key only) or already attached (mediaId). The first one is the cover. */
export interface Photo {
  key: string;
  url: string;
  mediaId?: number;
}

// Photos are shrunk in the browser before upload: phone photos are large and 1600 px is plenty for a listing
const MAX_SIDE = 1600;
const KEEP_AS_IS = 1.5 * 1024 * 1024;

async function shrink(file: File): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size <= KEEP_AS_IS) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    return blob ?? file;
  } catch {
    // Not decodable here (e.g. HEIC): send as is, the server says if it is not a supported photo
    return file;
  }
}

async function upload(file: File, isPrivate: boolean): Promise<Photo> {
  const body = new FormData();
  const blob = await shrink(file);
  body.append("file", blob, file.name.replace(/\.\w+$/, "") + ".jpg");
  if (isPrivate) body.append("private", "true");
  // multipart body: the generated type describes the fields as strings
  const res = await call(api.POST("/api/v1/owner/media", { body: body as unknown as { file: string; private: boolean } }));
  // A private document has no public address: preview the local copy
  return { key: res.key, url: isPrivate ? URL.createObjectURL(blob) : res.url };
}

/**
 * Photos from the seller's device: pick or drop several at once, see them right away, remove any.
 * Uploads happen as soon as photos are chosen; the listing only refers to them when it is saved.
 */
export function PhotoPicker({
  photos,
  onChange,
  max = 10,
  disabled = false,
  isPrivate = false,
  label = "Ảnh căn",
  hint = "Ảnh đầu tiên là ảnh bìa · JPG, PNG, WebP",
}: {
  photos: Photo[];
  onChange: (next: Photo[]) => void;
  max?: number;
  disabled?: boolean;
  /** Identity / authorisation documents: only the uploader and the investor can open them */
  isPrivate?: boolean;
  label?: string;
  hint?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  // Latest list while uploads finish one by one
  const current = useRef(photos);
  current.current = photos;

  async function add(files: FileList | File[]) {
    setError(null);
    const room = max - current.current.length;
    const chosen = [...files].filter((f) => f.type.startsWith("image/") || /\.(heic|heif)$/i.test(f.name));
    if (chosen.length < [...files].length) setError("Chỉ chọn được tệp ảnh (JPG, PNG, WebP).");
    if (chosen.length > room) setError(`Mỗi tin tối đa ${max} ảnh.`);
    for (const file of chosen.slice(0, Math.max(0, room))) {
      setUploading((n) => n + 1);
      try {
        const photo = await upload(file, isPrivate);
        current.current = [...current.current, photo];
        onChange(current.current);
      } catch (e) {
        setError(`${file.name}: ${errorMessage(e)}`);
      } finally {
        setUploading((n) => n - 1);
      }
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!disabled) void add(e.dataTransfer.files);
  }

  const full = photos.length + uploading >= max;

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <p className="font-semibold">
          {label} <span className="font-normal text-muted">({photos.length}/{max})</span>
        </p>
        <p className="text-xs text-muted">{hint}</p>
      </div>
      <ul
        className={`grid grid-cols-2 gap-3 rounded-3xl p-1 transition sm:grid-cols-4 ${dragging ? "bg-brand-50 ring-2 ring-brand-500" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        {photos.map((p, i) => (
          <li key={p.key} className="group relative aspect-[4/3] overflow-hidden rounded-2xl bg-sand">
            <img src={p.url} alt={`Ảnh ${i + 1}`} className="h-full w-full object-cover" />
            {i === 0 && !isPrivate && (
              <span className="absolute left-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-semibold text-white">
                Ảnh bìa
              </span>
            )}
            {!disabled && (
              <button
                type="button"
                onClick={() => onChange(photos.filter((x) => x.key !== p.key))}
                className="absolute right-2 top-2 grid size-7 place-items-center rounded-full bg-black/60 text-sm text-white hover:bg-black/80"
                aria-label={`Bỏ ảnh ${i + 1}`}
              >
                ✕
              </button>
            )}
          </li>
        ))}
        {Array.from({ length: uploading }, (_, i) => (
          <li key={`up-${i}`} className="grid aspect-[4/3] animate-pulse place-items-center rounded-2xl bg-sand text-xs text-muted">
            Đang tải ảnh…
          </li>
        ))}
        {!disabled && !full && (
          <li>
            <button
              type="button"
              onClick={() => input.current?.click()}
              className="grid aspect-[4/3] w-full place-items-center rounded-2xl border-2 border-dashed border-brand-200 bg-paper text-center text-sm text-brand-700 transition hover:border-brand-500 hover:bg-brand-50"
            >
              <span>
                <span className="block text-2xl leading-none">＋</span>
                <span className="mt-1 block font-semibold">Thêm ảnh</span>
                <span className="block text-xs text-muted">hoặc kéo thả vào đây</span>
              </span>
            </button>
          </li>
        )}
      </ul>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) void add(e.target.files);
          e.target.value = "";
        }}
      />
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
    </div>
  );
}
