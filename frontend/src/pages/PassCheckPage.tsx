import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { api, call } from "../api/client";
import type { components } from "../api/schema";
import { formatTimeRange } from "../lib/format";

type Check = components["schemas"]["PassCheckOut"];

const LOOK: Record<Check["result"], { title: string; tone: string; icon: string }> = {
  valid: { title: "Hợp lệ — mời vào", tone: "bg-emerald-600", icon: "✓" },
  too_early: { title: "Chưa tới giờ hẹn", tone: "bg-amber-500", icon: "⏳" },
  expired: { title: "Đã hết hiệu lực", tone: "bg-red-600", icon: "✕" },
  cancelled: { title: "Lịch xem đã hủy", tone: "bg-red-600", icon: "✕" },
  invalid: { title: "Mã không hợp lệ", tone: "bg-red-600", icon: "✕" },
};

/**
 * Opened by the guard's / reception's phone camera from the buyer's QR (public, no sign-in): whether to let the
 * buyer in now, which home, and who meets whom. Never shows a phone number.
 */
export function PassCheckPage() {
  const token = useParams().token ?? "";
  const check = useQuery({
    queryKey: ["pass-check", token],
    queryFn: () => call(api.GET("/api/v1/passes/{token}", { params: { path: { token } } })),
    // Re-check while the page stays open (e.g. "too early" becomes "valid")
    refetchInterval: 60_000,
  });

  return (
    <div className="min-h-dvh bg-slate-100 px-4 py-6 text-slate-900">
      <div className="mx-auto max-w-md space-y-4">
        <p className="text-center text-sm font-semibold uppercase tracking-widest text-slate-500">BookingBot · Kiểm tra mã vào cửa</p>

        {check.isPending && <p className="rounded-2xl bg-white p-8 text-center shadow-sm">Đang kiểm tra mã…</p>}
        {check.isError && (
          <p className="rounded-2xl bg-white p-8 text-center shadow-sm">
            Không kiểm tra được mã (lỗi kết nối). Vui lòng thử lại hoặc liên hệ ban quản lý tòa nhà.
          </p>
        )}

        {check.data && (
          <>
            <div className={`rounded-3xl ${LOOK[check.data.result].tone} p-6 text-center text-white shadow-lg`}>
              <p className="text-5xl font-bold leading-none" aria-hidden="true">
                {LOOK[check.data.result].icon}
              </p>
              <h1 className="mt-3 text-2xl font-bold">{LOOK[check.data.result].title}</h1>
              <p className="mt-1 text-white/90">{check.data.message}</p>
            </div>

            {check.data.unit_code && (
              <dl className="divide-y divide-slate-100 rounded-3xl bg-white shadow-sm">
                <Row label="Căn hộ" value={`${check.data.unit_code} · Tầng ${check.data.floor}`} big />
                <Row label="Tòa / dự án" value={`${check.data.building} · ${check.data.project}`} />
                {check.data.start_at && check.data.end_at && (
                  <Row label="Giờ hẹn xem" value={formatTimeRange(check.data.start_at, check.data.end_at)} />
                )}
                <Row label="Người xem nhà" value={check.data.buyer_name ?? "—"} />
                <Row label="Chủ nhà (người tiếp)" value={check.data.seller_name ?? "—"} />
                <Row label="Mã lịch hẹn" value={check.data.deal_code ?? "—"} mono />
              </dl>
            )}
            <p className="px-2 text-center text-xs text-slate-500">
              Trang này chỉ dùng để xác nhận lịch hẹn xem nhà và đưa khách tới đúng căn; không hiển thị số điện thoại.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, big = false, mono = false }: { label: string; value: string; big?: boolean; mono?: boolean }) {
  return (
    <div className="px-5 py-3.5">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={`${big ? "text-2xl font-bold" : "font-semibold"} ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}
