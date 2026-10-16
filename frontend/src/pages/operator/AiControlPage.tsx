import { useQuery } from "@tanstack/react-query";

import { api, call } from "../../api/client";
import { ErrorBox, Notice, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

/**
 * Read only: whether buyers can chat with the AI assistant. The dev team turns it off and on (kill switch through
 * the admin API) when they see a technical problem; operators see it here because support calls may rise while
 * the assistant is off. Booking, owner confirmation and every other flow keep working either way.
 */
export function AiControlPage() {
  const status = useQuery({
    queryKey: ["operator-ai-assistant"],
    queryFn: () => call(api.GET("/api/v1/operator/ai-assistant")),
    refetchInterval: 30_000,
  });

  if (status.isPending) return <Spinner />;
  if (status.isError) return <ErrorBox error={status.error} onRetry={() => status.refetch()} />;
  const s = status.data;

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Trợ lý AI"
        subtitle="Trạng thái Trợ lý AI của người mua. Việc bật/tắt do đội kỹ thuật thực hiện khi có sự cố."
      />

      <section className="card space-y-5 p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className={`size-3 rounded-full ${s.enabled ? "bg-emerald-500" : "bg-red-500"}`} aria-hidden="true" />
          <div>
            <p className="text-lg font-semibold">{s.enabled ? "Đang hoạt động" : "Đang tạm dừng (bảo trì)"}</p>
            {s.updated_at && <p className="text-sm text-muted">Thay đổi lần cuối: {formatDateTime(s.updated_at)}</p>}
          </div>
        </div>

        {!s.enabled && (
          <Notice tone="danger">
            Người mua hiện không chat được với Trợ lý AI và được hướng dẫn gọi Tổng đài <strong>{s.hotline}</strong>.
            {s.reason && <> Lý do: {s.reason}.</>} Đặt lịch, xác nhận lịch và các chức năng khác vẫn hoạt động bình
            thường.
          </Notice>
        )}

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
