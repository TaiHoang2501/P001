import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../api/client";
import type { Booking } from "../api/types";
import { ErrorBox, Notice } from "../components/ui";

/**
 * What the buyer can do once the viewing time is over: say how they found the home (when it took place), or
 * disagree with what was recorded ("I came" / "the owner was not there"); a disagreement goes to the investor.
 */
export function AfterViewing({ booking: b, onChanged }: { booking: Booking; onChanged?: (b: Booking) => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [disputing, setDisputing] = useState(false);
  const [sent, setSent] = useState(false);
  const path = { params: { path: { booking_id: b.id } } };
  const done = (next: Booking) => {
    queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
    queryClient.invalidateQueries({ queryKey: ["my-activity"] });
    queryClient.invalidateQueries({ queryKey: ["deal", b.deal_id] });
    onChanged?.(next);
  };
  const feedback = useMutation({
    mutationFn: (interest: "INTERESTED" | "NOT_SUITABLE") =>
      call(api.POST("/api/v1/bookings/{booking_id}/feedback", { ...path, body: { interest, note: note.trim() } })),
    onSuccess: done,
  });
  const dispute = useMutation({
    mutationFn: (claim: "I_CAME" | "OWNER_ABSENT") =>
      call(api.POST("/api/v1/bookings/{booking_id}/dispute", { ...path, body: { claim, note: note.trim() } })),
    onSuccess: (next) => {
      setSent(true);
      setDisputing(false);
      done(next);
    },
  });
  const error = feedback.error ?? dispute.error;
  const over = new Date(b.end_at).getTime() <= Date.now();

  const disputeForm = (claim: "I_CAME" | "OWNER_ABSENT", label: string, placeholder: string) =>
    disputing ? (
      <div className="space-y-2">
        <textarea
          className="input"
          rows={2}
          maxLength={1000}
          placeholder={placeholder}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary btn-sm" disabled={dispute.isPending} onClick={() => dispute.mutate(claim)}>
            {dispute.isPending ? "Đang gửi..." : "Gửi cho Chủ đầu tư kiểm tra"}
          </button>
          <button type="button" className="btn-secondary btn-sm" onClick={() => setDisputing(false)}>
            Thôi
          </button>
        </div>
      </div>
    ) : (
      <button type="button" className="text-sm font-semibold text-brand-700 underline" onClick={() => setDisputing(true)}>
        {label}
      </button>
    );

  let body = null;
  if (sent) {
    body = <Notice tone="success">Đã gửi. Chủ đầu tư sẽ liên hệ hai bên và báo kết quả cho bạn.</Notice>;
  } else if (b.sold_to_other && (b.status === "COMPLETED" || (b.status === "CONFIRMED" && over))) {
    // Sold to someone else after this viewing: nothing left to say about it (the buyer it went to keeps the buttons)
    body = <Notice tone="warning">Căn này đã được bán cho người mua khác. Nhắn Trợ lý AI để tìm căn tương tự.</Notice>;
  } else if (b.status === "CONFIRMED" && over) {
    body = (
      <>
        <p className="text-sm">Buổi xem đã qua. Chủ căn sẽ ghi nhận kết quả, sau đó bạn cho biết cảm nhận về căn.</p>
        {disputeForm("OWNER_ABSENT", "Bạn đến nhưng chủ căn không có mặt?", "VD: Tôi đến lúc 14h, gọi cửa không ai mở")}
      </>
    );
  } else if (b.status === "COMPLETED" && b.deal_status === "VIEWED") {
    body = (
      <>
        <p className="font-semibold">Bạn thấy căn này thế nào?</p>
        <textarea
          className="input"
          rows={2}
          maxLength={1000}
          placeholder="Ghi chú thêm (không bắt buộc), VD: thích view nhưng bếp hơi nhỏ"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary btn-sm" disabled={feedback.isPending} onClick={() => feedback.mutate("INTERESTED")}>
            Tôi quan tâm
          </button>
          <button type="button" className="btn-secondary btn-sm" disabled={feedback.isPending} onClick={() => feedback.mutate("NOT_SUITABLE")}>
            Chưa phù hợp
          </button>
        </div>
        <p className="text-xs text-muted">
          Quan tâm: chủ căn được báo. Chưa phù hợp: Trợ lý AI tìm căn khác cho bạn trong khung chat.
        </p>
      </>
    );
  } else if (b.status === "COMPLETED" && b.deal_status === "INTERESTED") {
    body = <Notice tone="success">Bạn đã báo quan tâm căn này; chủ căn đã được báo.</Notice>;
  } else if (b.status === "NO_SHOW") {
    body = (
      <>
        <p className="text-sm">Chủ căn ghi nhận bạn không đến buổi xem này.</p>
        {disputeForm("I_CAME", "Thực ra bạn có đến?", "VD: Tôi đến lúc 14h05, đã gặp bảo vệ toà nhà")}
      </>
    );
  } else if (b.status === "OWNER_ABSENT") {
    body = <Notice tone="warning">Chủ đầu tư xác định chủ căn không có mặt ở buổi xem này. Xin lỗi vì bất tiện; nhắn Trợ lý AI để đặt lại.</Notice>;
  } else if (b.status === "UNREPORTED") {
    body = <p className="text-sm text-muted">Không ai ghi nhận kết quả buổi xem này nên lịch đã tự đóng.</p>;
  }
  if (!body) return null;

  return (
    <div className="space-y-2 rounded-xl border border-line bg-slate-50 p-3" aria-label="Sau buổi xem">
      {error && <ErrorBox error={error} />}
      {body}
    </div>
  );
}

/** Does this viewing wait for something from the buyer (or for the owner to record it)? */
export function needsBuyerAfterViewing(b: Booking): boolean {
  if (b.sold_to_other) return false;
  return (
    (b.status === "COMPLETED" && b.deal_status === "VIEWED") ||
    b.status === "NO_SHOW" ||
    (b.status === "CONFIRMED" && new Date(b.end_at).getTime() <= Date.now())
  );
}
