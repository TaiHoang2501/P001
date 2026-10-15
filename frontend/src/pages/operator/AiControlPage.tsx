import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, call } from "../../api/client";
import { ErrorBox, Notice, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

/**
 * AI kill switch: the operator turns the buyer's AI assistant off at once (wrong answers, model provider down,
 * abuse) and back on. While off, the buyer chat shows the maintenance notice with the support hotline; booking,
 * owner confirmation and every other flow keep working. Each change is audited.
 */
export function AiControlPage() {
  const queryClient = useQueryClient();
  const [confirmOff, setConfirmOff] = useState(false);
  const status = useQuery({
    queryKey: ["operator-ai-assistant"],
    queryFn: () => call(api.GET("/api/v1/operator/ai-assistant")),
    refetchInterval: 30_000,
  });
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => call(api.PUT("/api/v1/operator/ai-assistant", { body: { enabled } })),
    onSuccess: (data) => {
      setConfirmOff(false);
      queryClient.setQueryData(["operator-ai-assistant"], data);
      queryClient.invalidateQueries({ queryKey: ["assistant-status"] });
    },
  });

  if (status.isPending) return <Spinner />;
  if (status.isError) return <ErrorBox error={status.error} onRetry={() => status.refetch()} />;
  const s = status.data;

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Trợ lý AI"
        subtitle="Tắt khẩn cấp Trợ lý AI của người mua khi có sự cố; các chức năng đặt lịch, xác nhận lịch vẫn hoạt động."
      />

      <section className="card space-y-5 p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className={`size-3 rounded-full ${s.enabled ? "bg-emerald-500" : "bg-red-500"}`}
              aria-hidden="true"
            />
            <div>
              <p className="text-lg font-semibold">{s.enabled ? "Đang hoạt động" : "Đã tắt (bảo trì)"}</p>
              {s.updated_at && <p className="text-sm text-muted">Thay đổi lần cuối: {formatDateTime(s.updated_at)}</p>}
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={s.enabled}
            aria-label="Bật / tắt Trợ lý AI"
            disabled={toggle.isPending}
            onClick={() => (s.enabled ? setConfirmOff(true) : toggle.mutate(true))}
            className={`relative h-8 w-14 shrink-0 rounded-full transition disabled:opacity-50 ${
              s.enabled ? "bg-emerald-500" : "bg-slate-300"
            }`}
          >
            <span
              className={`absolute top-1 size-6 rounded-full bg-white shadow transition-all ${s.enabled ? "left-7" : "left-1"}`}
            />
          </button>
        </div>

        {confirmOff && (
          <Notice tone="danger">
            <p>
              Tắt Trợ lý AI ngay? Người mua sẽ không chat được với AI và thấy thông báo bảo trì kèm số Tổng đài{" "}
              <strong>{s.hotline}</strong>.
            </p>
            <div className="mt-3 flex gap-2">
              <button type="button" className="btn-danger btn-sm" disabled={toggle.isPending} onClick={() => toggle.mutate(false)}>
                Tắt AI
              </button>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirmOff(false)}>
                Hủy
              </button>
            </div>
          </Notice>
        )}

        {toggle.isError && <ErrorBox error={toggle.error} />}

        <div className="space-y-1 text-sm">
          <p className="font-medium">Người mua đang thấy trong khung chat:</p>
          <p className="rounded-lg bg-slate-50 p-3 text-muted">
            {s.enabled ? "Trợ lý AI trả lời bình thường." : s.message}
          </p>
        </div>
      </section>
    </div>
  );
}
