import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { api, call } from "../../api/client";
import type { Escalation } from "../../api/types";
import { ErrorBox, Spinner } from "../../components/ui";
import { SUPPORT_REASONS } from "../owner/OwnershipSupport";

const BOOK_STATUS: Record<string, { label: string; tone: string }> = {
  UNVERIFIED: { label: "Chưa xác thực", tone: "bg-stone-100 text-stone-700" },
  OTP_SENT: { label: "Đã gửi OTP", tone: "bg-sky-100 text-sky-900" },
  VERIFIED: { label: "Đã xác thực", tone: "bg-emerald-100 text-emerald-800" },
  FAILED: { label: "Bị khóa (sai OTP)", tone: "bg-red-100 text-red-800" },
};

/**
 * An ownership support case: what the seller asked, their documents, the red book as it stands now, and the
 * operator's actions (unlock / new phone, verify by hand, revoke a wrong verification).
 */
export function OwnershipCase({ escalation: e }: { escalation: Escalation }) {
  const queryClient = useQueryClient();
  const open = e.status === "OPEN" || e.status === "IN_PROGRESS";
  const path = { params: { path: { escalation_id: e.id } } };
  const state = useQuery({
    queryKey: ["ownership-case", e.id],
    queryFn: () => call(api.GET("/api/v1/operator/escalations/{escalation_id}/ownership", path)),
  });
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [revokeReason, setRevokeReason] = useState("");
  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["ownership-case", e.id] });
    queryClient.invalidateQueries({ queryKey: ["escalations"] });
  };
  const unlock = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/operator/escalations/{escalation_id}/ownership/unlock", { ...path, body: { owner_phone: phone.trim() || null } })),
    onSuccess: done,
  });
  const verify = useMutation({
    mutationFn: () => call(api.POST("/api/v1/operator/escalations/{escalation_id}/ownership/verify", { ...path, body: { note } })),
    onSuccess: done,
  });
  const revoke = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/operator/escalations/{escalation_id}/ownership/revoke", { ...path, body: { note: revokeReason } })),
    onSuccess: () => {
      setRevokeReason("");
      done();
    },
  });
  const busy = unlock.isPending || verify.isPending || revoke.isPending;
  const error = unlock.error ?? verify.error ?? revoke.error;

  const ctx = e.context as { reason?: string; red_book_code?: string; red_book_holder_name?: string; note?: string; documents?: string[] };
  const reason = SUPPORT_REASONS.find((r) => r.value === ctx.reason);
  const book = state.data?.red_book;
  const seller = state.data?.seller;
  const heldByOther = book?.status === "VERIFIED" && book.verified_by_id !== seller?.id;

  return (
    <div className="grid gap-3 rounded-xl bg-stone-50 p-3 text-sm md:grid-cols-2">
      <section>
        <h4 className="font-semibold">Yêu cầu của người bán</h4>
        <dl className="mt-1 space-y-0.5">
          <Row label="Vấn đề" value={reason?.label ?? ctx.reason ?? ""} />
          <Row label="Người đứng tên" value={ctx.red_book_holder_name ?? ""} />
          <Row label="Mã sổ / hợp đồng" value={ctx.red_book_code ?? ""} mono />
          {seller && <Row label="Người bán" value={`${seller.full_name} · ${seller.phone ?? "không có SĐT"} · #${seller.id}`} />}
        </dl>
        {ctx.note && <p className="mt-2 rounded-lg bg-white px-3 py-2">“{ctx.note}”</p>}
        <Documents keys={ctx.documents ?? []} />
      </section>

      <section>
        <h4 className="font-semibold">Sổ đỏ trong dữ liệu Chủ đầu tư</h4>
        {state.isPending && <Spinner />}
        {state.data && !book && (
          <p className="mt-1 text-muted">Mã này không có trong dữ liệu (ví dụ căn chưa có sổ). Xác thực thủ công sẽ thêm sổ cho người bán.</p>
        )}
        {book && (
          <dl className="mt-1 space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="font-mono font-semibold">{book.red_book_code}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${BOOK_STATUS[book.status].tone}`}>
                {BOOK_STATUS[book.status].label}
              </span>
            </div>
            <Row label="Người đứng tên" value={book.red_book_holder_name} />
            <Row label="SĐT chủ sở hữu" value={book.owner_phone} mono />
            <Row label="Số lần nhập sai OTP" value={String(book.otp_attempts)} />
            {book.verified_by_name && <Row label="Đang thuộc tài khoản" value={`${book.verified_by_name} (#${book.verified_by_id})`} />}
            {book.property_label && <Row label="Tin đăng" value={book.property_label} />}
          </dl>
        )}
      </section>

      {open && state.data && (
        <div className="space-y-2 border-t border-stone-200 pt-3 md:col-span-2">
          {error && <ErrorBox error={error} />}
          {book && book.status !== "VERIFIED" && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                className="input w-56"
                inputMode="tel"
                placeholder="SĐT mới của chủ sở hữu (nếu đổi)"
                value={phone}
                onChange={(ev) => setPhone(ev.target.value.replace(/[^\d]/g, ""))}
              />
              <button type="button" className="btn-secondary btn-sm" disabled={busy || (phone !== "" && phone.length < 10)} onClick={() => unlock.mutate()}>
                {phone ? "Cập nhật SĐT & mở khóa" : "Mở khóa sổ"}
              </button>
              <span className="text-xs text-muted">Người bán tự làm lại bước OTP</span>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="input min-w-0 flex-1"
              placeholder="Đã kiểm tra gì? VD: Đã đối chiếu giấy ủy quyền công chứng và CCCD"
              value={note}
              onChange={(ev) => setNote(ev.target.value)}
            />
            <button
              type="button"
              className="btn-primary btn-sm"
              disabled={busy || heldByOther || note.trim().length < 3}
              title={heldByOther ? "Sổ đang thuộc tài khoản khác: thu hồi trước" : undefined}
              onClick={() => verify.mutate()}
            >
              Xác thực thủ công
            </button>
          </div>
          {book?.status === "VERIFIED" && book.verified_by_id !== null && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                className="input min-w-0 flex-1"
                placeholder="Lý do thu hồi (người đang giữ sổ sẽ thấy)"
                value={revokeReason}
                onChange={(ev) => setRevokeReason(ev.target.value)}
              />
              <button
                type="button"
                className="btn-danger btn-sm"
                disabled={busy || revokeReason.trim().length < 3}
                onClick={() => {
                  if (
                    window.confirm(
                      `Thu hồi xác thực sổ ${book.red_book_code} của ${book.verified_by_name}?` +
                        (book.property_id ? " Tin đăng sẽ bị gỡ và các lịch xem của căn bị hủy." : ""),
                    )
                  )
                    revoke.mutate();
                }}
              >
                Thu hồi xác thực
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="w-36 shrink-0 text-muted">{label}</dt>
      <dd className={`min-w-0 break-words ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

/** Private documents: fetched with the operator's sign-in (never public URLs), opened over the page. */
function Documents({ keys }: { keys: string[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (keys.length === 0) return <p className="mt-2 text-xs text-muted">Không kèm giấy tờ.</p>;
  return (
    <div className="mt-2">
      <p className="text-xs text-muted">Giấy tờ kèm theo ({keys.length})</p>
      <div className="mt-1 flex flex-wrap gap-2">
        {keys.map((k) => (
          <PrivateImage key={k} mediaKey={k} className="h-16 w-20 cursor-zoom-in rounded-lg object-cover ring-1 ring-stone-200" onClick={setOpen} />
        ))}
      </div>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-50 grid place-items-center bg-black/90 p-6" role="dialog" aria-modal="true" onClick={() => setOpen(null)}>
            <img src={open} alt="Giấy tờ" className="max-h-full max-w-full rounded-xl object-contain" />
          </div>,
          document.body,
        )}
    </div>
  );
}

function PrivateImage({ mediaKey, className, onClick }: { mediaKey: string; className: string; onClick: (url: string) => void }) {
  const id = mediaKey.split("/").pop()!;
  const file = useQuery({
    queryKey: ["private-doc", id],
    queryFn: () => call(api.GET("/api/v1/media/{media_id}/private", { params: { path: { media_id: id } }, parseAs: "blob" })),
    staleTime: Infinity,
  });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!(file.data instanceof Blob)) return;
    const u = URL.createObjectURL(file.data);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file.data]);
  if (!url) return <span className={`${className} grid place-items-center bg-stone-100 text-[10px] text-muted`}>…</span>;
  return <img src={url} alt="Giấy tờ" className={className} onClick={() => onClick(url)} />;
}
