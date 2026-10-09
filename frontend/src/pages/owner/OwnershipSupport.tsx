import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, call } from "../../api/client";
import type { components } from "../../api/schema";
import { PhotoPicker, type Photo } from "../../components/PhotoPicker";
import { ErrorBox, Notice } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

export type SupportReason = components["schemas"]["OwnershipSupportCreate"]["reason"];

/** Why the automatic check (holder + code + OTP) cannot work, and what to attach for the investor to decide. */
export const SUPPORT_REASONS: { value: SupportReason; label: string; attach: string }[] = [
  { value: "NO_OTP", label: "Không nhận được mã OTP (chủ sở hữu đã đổi số)", attach: "CCCD của chủ sở hữu và số điện thoại mới (ghi ở phần mô tả)" },
  { value: "LOCKED", label: "Sổ đỏ / sổ hồng bị khóa do nhập sai OTP", attach: "CCCD của chủ sở hữu" },
  { value: "MISMATCH", label: "Thông tin đúng nhưng hệ thống báo không khớp", attach: "Ảnh trang đầu sổ đỏ / sổ hồng và CCCD" },
  { value: "PROXY", label: "Bán thay chủ sở hữu (có giấy ủy quyền)", attach: "Giấy ủy quyền có công chứng và CCCD hai bên" },
  { value: "CO_OWNER", label: "Sổ đồng sở hữu", attach: "Ảnh sổ đỏ / sổ hồng và văn bản đồng ý bán của người đồng sở hữu" },
  { value: "INHERITANCE", label: "Thừa kế, chưa sang tên", attach: "Văn bản thừa kế, giấy chứng tử và CCCD" },
  { value: "NO_RED_BOOK", label: "Căn chưa có sổ đỏ / sổ hồng (chỉ có hợp đồng mua bán)", attach: "Hợp đồng mua bán và biên bản bàn giao căn" },
  { value: "CLAIMED_BY_OTHER", label: "Sổ đỏ / sổ hồng đã bị một tài khoản khác xác thực", attach: "Ảnh sổ đỏ / sổ hồng gốc và CCCD của chủ sở hữu" },
  { value: "OTHER", label: "Lý do khác", attach: "Giấy tờ liên quan" },
];

export interface SupportPrefill {
  reason: SupportReason;
  holder: string;
  code: string;
}

/** Ask the investor for help with a red book; documents are private (only the investor sees them). */
export function SupportForm({ prefill, onClose }: { prefill: SupportPrefill; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState<SupportReason>(prefill.reason);
  const [holder, setHolder] = useState(prefill.holder);
  const [code, setCode] = useState(prefill.code);
  const [note, setNote] = useState("");
  const [documents, setDocuments] = useState<Photo[]>([]);
  const chosen = SUPPORT_REASONS.find((r) => r.value === reason)!;
  const noBook = reason === "NO_RED_BOOK";

  const send = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/owner/ownership/support", {
          body: {
            reason,
            red_book_holder_name: holder.trim(),
            red_book_code: code.trim(),
            note: note.trim(),
            documents: documents.map((d) => d.key),
          },
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ownership-support"] });
      onClose();
    },
  });

  return (
    <form
      className="h-fit space-y-4 rounded-[28px] bg-sand p-6"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        send.mutate();
      }}
    >
      <div>
        <h2 className="font-display text-2xl font-bold">Cần hỗ trợ xác thực</h2>
        <p className="mt-1 text-sm text-muted">
          Chủ đầu tư xem giấy tờ của bạn và xử lý, thường trong 1 ngày làm việc. Giấy tờ chỉ Chủ đầu tư xem được.
        </p>
      </div>
      {send.isError && <ErrorBox error={send.error} />}

      <fieldset>
        <legend className="label">Bạn gặp vấn đề gì?</legend>
        <div className="space-y-1.5">
          {SUPPORT_REASONS.map((r) => (
            <label
              key={r.value}
              className={`flex cursor-pointer items-start gap-2 rounded-2xl px-3 py-2 text-sm ${reason === r.value ? "bg-paper ring-2 ring-brand-500" : "hover:bg-paper/60"}`}
            >
              <input
                type="radio"
                name="support-reason"
                className="mt-0.5 accent-brand-600"
                checked={reason === r.value}
                onChange={() => setReason(r.value)}
              />
              {r.label}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor="sp-holder" className="label">
          {noBook ? "Họ tên người mua trên hợp đồng" : "Họ tên người đứng tên trên sổ"}
        </label>
        <input
          id="sp-holder"
          className="input rounded-full bg-paper px-4 py-2.5"
          required
          minLength={2}
          value={holder}
          onChange={(e) => setHolder(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="sp-code" className="label">
          {noBook ? "Số hợp đồng mua bán" : "Mã số sổ đỏ / sổ hồng"}
        </label>
        <input
          id="sp-code"
          className="input rounded-full bg-paper px-4 py-2.5 font-mono"
          required
          minLength={3}
          placeholder={noBook ? "HĐMB-2026-0042" : "SD-2017-0332211"}
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor="sp-note" className="label">
          Mô tả thêm
        </label>
        <textarea
          id="sp-note"
          rows={3}
          maxLength={2000}
          className="input bg-paper"
          placeholder={reason === "NO_OTP" ? "Số điện thoại mới của chủ sở hữu: 09…" : "Thông tin giúp Chủ đầu tư xử lý nhanh hơn"}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <PhotoPicker
        photos={documents}
        onChange={setDocuments}
        max={8}
        isPrivate
        label="Giấy tờ kèm theo"
        hint={`Nên có: ${chosen.attach}`}
      />

      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn-primary rounded-full px-5" disabled={send.isPending}>
          {send.isPending ? "Đang gửi..." : "Gửi yêu cầu hỗ trợ"}
        </button>
        <button type="button" className="btn-secondary rounded-full px-5" onClick={onClose}>
          Hủy
        </button>
      </div>
    </form>
  );
}

const STATUS: Record<string, { label: string; tone: string }> = {
  OPEN: { label: "Đang chờ xử lý", tone: "bg-amber-100 text-amber-900" },
  IN_PROGRESS: { label: "Chủ đầu tư đang xử lý", tone: "bg-sky-100 text-sky-900" },
  RESOLVED: { label: "Đã xử lý", tone: "bg-leaf text-leaf-ink" },
  DISMISSED: { label: "Đã đóng", tone: "bg-sand text-muted" },
};

/** The seller's support requests and what the investor did. */
export function SupportList() {
  const list = useQuery({
    queryKey: ["ownership-support"],
    queryFn: () => call(api.GET("/api/v1/owner/ownership/support")),
    refetchInterval: 60_000,
  });
  if (!list.data?.length) return null;
  return (
    <section className="h-fit rounded-[28px] bg-paper p-5" aria-labelledby="support-title">
      <h2 id="support-title" className="font-display text-xl font-bold">
        Yêu cầu hỗ trợ của bạn
      </h2>
      <ul className="mt-3 space-y-3">
        {list.data.map((e) => {
          const reason = SUPPORT_REASONS.find((r) => r.value === e.context.reason);
          const status = STATUS[e.status];
          return (
            <li key={e.id} className="rounded-2xl bg-canvas/60 p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono font-semibold">{String(e.context.red_book_code ?? "")}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.tone}`}>{status.label}</span>
              </div>
              <p className="mt-1 text-muted">
                {reason?.label} · gửi {formatDateTime(e.created_at)}
              </p>
              {e.resolution && (
                <Notice tone={e.status === "RESOLVED" ? "success" : "info"}>
                  <span className="font-semibold">Chủ đầu tư:</span> {e.resolution}
                </Notice>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
