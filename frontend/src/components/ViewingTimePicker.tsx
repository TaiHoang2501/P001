import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, call } from "../api/client";
import type { TimeWindow } from "../api/types";
import { formatTimeRange, timeOf, vnIso, vnToday } from "../lib/format";
import { ErrorBox, Notice } from "./ui";

interface Props {
  propertyId: number;
  /** Called with the chosen start time and the buyer's free window it came from */
  onPick: (startAt: string, buyerWindows: TimeWindow[]) => void;
  busy?: boolean;
  submitLabel: string;
}

/**
 * "When are you free?" -> buyer window ∩ seller availability (spec §4.8, AC-06).
 * Shows up to 3 proposed start times, or the seller's next free times when there is no overlap (AC-07).
 */
export function ViewingTimePicker({ propertyId, onPick, busy = false, submitLabel }: Props) {
  const [date, setDate] = useState(vnToday(1));
  const [from, setFrom] = useState("09:00");
  const [to, setTo] = useState("18:00");
  const [chosen, setChosen] = useState<string | null>(null);

  const windows: TimeWindow[] = [{ start_at: vnIso(date, from), end_at: vnIso(date, to) }];

  const find = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/properties/{property_id}/viewing-times", {
          params: { path: { property_id: propertyId } },
          body: { windows },
        }),
      ),
    onMutate: () => setChosen(null),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    find.mutate();
  }

  const result = find.data;
  const alternatives = result?.alternatives ?? [];
  const options = result ? (result.proposals.length > 0 ? result.proposals : alternatives) : [];

  return (
    <div className="space-y-3">
      <form onSubmit={onSubmit} className="space-y-2">
        <p className="label">Bạn rảnh khi nào?</p>
        <div className="grid grid-cols-[1fr_auto_auto] items-end gap-2">
          <div>
            <label htmlFor="vt-date" className="sr-only">
              Ngày
            </label>
            <input id="vt-date" type="date" className="input" min={vnToday()} value={date} onChange={(e) => setDate(e.target.value)} required />
          </div>
          <div>
            <label htmlFor="vt-from" className="sr-only">
              Từ
            </label>
            <input id="vt-from" type="time" className="input" step={1800} value={from} onChange={(e) => setFrom(e.target.value)} required />
          </div>
          <div>
            <label htmlFor="vt-to" className="sr-only">
              Đến
            </label>
            <input id="vt-to" type="time" className="input" step={1800} value={to} onChange={(e) => setTo(e.target.value)} required />
          </div>
        </div>
        <button type="submit" className="btn-secondary w-full" disabled={find.isPending || from >= to}>
          {find.isPending ? "Đang khớp lịch..." : "Tìm giờ xem phù hợp"}
        </button>
      </form>

      {find.isError && <ErrorBox error={find.error} />}

      {result && result.proposals.length === 0 && alternatives.length === 0 && (
        <Notice tone="warning">Chủ căn chưa có giờ trống trong 2 tuần tới. Hãy nhờ Trợ lý AI chuyển yêu cầu cho bộ phận hỗ trợ.</Notice>
      )}
      {result && result.proposals.length === 0 && alternatives.length > 0 && (
        <Notice tone="warning">Chủ căn không trống trong khung giờ bạn chọn. Các giờ trống gần nhất của chủ căn:</Notice>
      )}

      {options.length > 0 && (
        <fieldset>
          <legend className="label">{result!.proposals.length > 0 ? "Giờ xem khớp với cả hai bên" : "Giờ trống khác"}</legend>
          <div className="grid grid-cols-3 gap-1.5">
            {options.map((o) => (
              <button
                key={o.start_at}
                type="button"
                aria-pressed={chosen === o.start_at}
                title={formatTimeRange(o.start_at, o.end_at)}
                onClick={() => setChosen(o.start_at)}
                className={`rounded-lg border px-2 py-2 text-xs font-medium ${chosen === o.start_at ? "border-brand-600 bg-brand-600 text-white" : "border-line hover:border-brand-500"}`}
              >
                {result!.proposals.length > 0 ? timeOf(o.start_at) : formatTimeRange(o.start_at, o.end_at)}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {options.length > 0 && (
        <button
          type="button"
          className="btn-primary w-full"
          disabled={chosen === null || busy}
          onClick={() => chosen && onPick(chosen, result!.proposals.length > 0 ? windows : [])}
        >
          {busy ? "Đang gửi..." : chosen ? submitLabel : "Chọn một giờ xem"}
        </button>
      )}
    </div>
  );
}
