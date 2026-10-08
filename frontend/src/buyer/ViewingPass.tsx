import { useQuery } from "@tanstack/react-query";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { api, call } from "../api/client";
import type { Booking } from "../api/types";
import { formatTimeRange, timeOf } from "../lib/format";

/** "Vinhomes Ocean Park 1 · The Sapphire 1 - S1.08 · S1.08-2410" -> ["S1.08-2410", "The Sapphire 1 - S1.08 · …"] */
function place(b: Booking): { unit: string; where: string } {
  const [project, building, unit] = b.property_label.split(" · ");
  return { unit: unit ?? b.property_label, where: [building, project].filter(Boolean).join(" · ") };
}

/**
 * Entry pass for a confirmed viewing: a QR the buyer shows to the building's guard or reception. Scanning it
 * opens /pass/{token}, which tells them whether to let the buyer in now and which home to take them to.
 */
export function ViewingPass({ booking: b }: { booking: Booking }) {
  const pass = useQuery({
    queryKey: ["viewing-pass", b.id, b.start_at],
    queryFn: () => call(api.GET("/api/v1/bookings/{booking_id}/pass", { params: { path: { booking_id: b.id } } })),
    staleTime: 10 * 60_000,
  });
  const [qr, setQr] = useState<string | null>(null);
  const [big, setBig] = useState(false);
  const url = pass.data ? `${window.location.origin}/pass/${pass.data.token}` : null;

  useEffect(() => {
    if (!url) return;
    QRCode.toDataURL(url, { width: 640, margin: 1, errorCorrectionLevel: "M" })
      .then(setQr)
      .catch(() => setQr(null));
  }, [url]);

  if (pass.isError) return null; // not confirmed (yet): no pass
  const { unit, where } = place(b);

  return (
    <section className="rounded-2xl border border-brand-200 bg-brand-50/60 p-4" aria-label="Mã vào cửa">
      <div className="flex gap-4">
        <button
          type="button"
          onClick={() => qr && setBig(true)}
          className="grid size-28 shrink-0 place-items-center overflow-hidden rounded-xl bg-white p-1.5 shadow-sm ring-1 ring-line"
          aria-label="Phóng to mã QR"
        >
          {qr ? <img src={qr} alt="" className="size-full" /> : <span className="text-xs text-muted">Đang tạo mã…</span>}
        </button>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-semibold">Mã vào cửa</p>
          <p className="text-sm text-muted">
            Đưa mã này cho bảo vệ hoặc lễ tân {where.split(" · ")[0]} khi tới xem căn <strong className="text-ink">{unit}</strong>.
          </p>
          {pass.data && (
            <p className="text-xs text-muted">
              Hiệu lực từ {timeOf(pass.data.valid_from)} đến {timeOf(pass.data.valid_until)} ngày xem.
            </p>
          )}
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              disabled={!qr}
              onClick={() => setBig(true)}
              className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Phóng to
            </button>
            {qr && (
              <a
                href={qr}
                download={`ma-vao-cua-${b.deal_code}.png`}
                className="rounded-lg border border-line bg-white px-3 py-1.5 text-xs font-semibold hover:border-brand-500"
              >
                Tải ảnh QR
              </a>
            )}
          </div>
        </div>
      </div>

      {big &&
        qr &&
        createPortal(
          // Full screen and bright, easy for the guard's phone to read
          <div
            className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-5 bg-white p-6 text-center"
            role="dialog"
            aria-modal="true"
            aria-label="Mã vào cửa"
            onClick={() => setBig(false)}
          >
            <p className="text-sm font-semibold uppercase tracking-widest text-muted">Mã vào cửa · BookingBot</p>
            <img src={qr} alt={`Mã QR vào cửa xem căn ${unit}`} className="w-[min(80vw,26rem)]" />
            <div>
              <p className="text-2xl font-bold">Căn {unit}</p>
              <p className="text-muted">{where}</p>
              <p className="mt-1 font-semibold">{formatTimeRange(b.start_at, b.end_at)}</p>
              <p className="font-mono text-sm text-muted">{b.deal_code}</p>
            </div>
            <button type="button" className="rounded-full border border-line px-5 py-2 text-sm font-semibold">
              Đóng
            </button>
          </div>,
          document.body,
        )}
    </section>
  );
}
