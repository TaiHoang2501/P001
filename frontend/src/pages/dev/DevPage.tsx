import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { adminCall, type AssistantControl, type DevMetrics } from "../../api/admin";
import { ApiError, errorMessage } from "../../api/client";
import { ErrorBox, Notice, PageHeader, Spinner } from "../../components/ui";
import { BOOKING_STATUS, DEAL_STATUS, PROPERTY_STATUS, ROLE, formatDateTime } from "../../lib/format";

/**
 * Developer page (/dev): AI assistant health and the business flow, plus the AI kill switch. Not linked from any
 * role's menu; it is unlocked with ADMIN_API_TOKEN, kept for this browser tab only (sessionStorage).
 */

const TOKEN_KEY = "bookingbot.devToken";
const PERIODS = [1, 3, 30, 90];

function readToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveToken(value: string) {
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Private mode: the token lives in memory until the page reloads
  }
}

export function DevPage() {
  const [token, setToken] = useState(readToken);
  useEffect(() => {
    document.title = "Dev · BookingBot";
    return () => {
      document.title = "BookingBot";
    };
  }, []);
  const lock = () => {
    saveToken("");
    setToken("");
  };
  if (!token) return <TokenGate onUnlock={(t) => (saveToken(t), setToken(t))} />;
  return <Dashboard token={token} onLock={lock} />;
}

function TokenGate({ onUnlock }: { onUnlock: (token: string) => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Check the token before keeping it
      await adminCall<AssistantControl>(value.trim(), "/ai-assistant");
      onUnlock(value.trim());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Trang dành cho dev" subtitle="Nhập ADMIN_API_TOKEN để xem số liệu và bật/tắt Trợ lý AI." />
      <form onSubmit={submit} className="card space-y-4 p-5">
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Admin token</span>
          <input
            type="password"
            className="input w-full"
            autoComplete="off"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
        </label>
        {error != null && <Notice tone="danger">{tokenError(error)}</Notice>}
        <button type="submit" className="btn-primary w-full" disabled={busy || !value.trim()}>
          {busy ? "Đang kiểm tra..." : "Mở bảng điều khiển"}
        </button>
        <p className="text-xs text-muted">Token chỉ được giữ trong tab này và mất khi đóng tab.</p>
      </form>
    </div>
  );
}

function tokenError(err: unknown): string {
  if (err instanceof ApiError && err.status === 401) return "Token không đúng.";
  if (err instanceof ApiError && err.status === 403) return "API dev đang tắt trên máy chủ (chưa đặt ADMIN_API_TOKEN).";
  return errorMessage(err);
}

function Dashboard({ token, onLock }: { token: string; onLock: () => void }) {
  const [days, setDays] = useState(3);
  const metrics = useQuery({
    queryKey: ["dev-metrics", token, days],
    queryFn: () => adminCall<DevMetrics>(token, `/metrics?days=${days}`),
    refetchInterval: 30_000,
    retry: (count, err) => !(err instanceof ApiError && err.status === 401) && count < 2,
  });
  // A token that stopped working (rotated on the server): back to the token form
  useEffect(() => {
    if (metrics.error instanceof ApiError && metrics.error.status === 401) onLock();
  }, [metrics.error, onLock]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Giám sát hệ thống"
        subtitle={
          metrics.data ? `Cập nhật ${formatDateTime(metrics.data.generated_at)} · tự làm mới mỗi 30 giây` : undefined
        }
        action={
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-line bg-white p-0.5 text-sm" role="group" aria-label="Khoảng thời gian">
              {PERIODS.map((d) => (
                <button
                  key={d}
                  type="button"
                  aria-pressed={days === d}
                  onClick={() => setDays(d)}
                  className={`rounded-md px-2.5 py-1 ${days === d ? "bg-brand-600 text-white" : "text-muted hover:text-ink"}`}
                >
                  {d === 1 ? "24 giờ" : `${d} ngày`}
                </button>
              ))}
            </div>
            <button type="button" className="btn-secondary btn-sm" onClick={onLock}>
              Khóa
            </button>
          </div>
        }
      />

      {metrics.isPending && <Spinner />}
      {metrics.isError && <ErrorBox error={metrics.error} onRetry={() => metrics.refetch()} />}
      {metrics.data && (
        <>
          <KillSwitch token={token} status={metrics.data.assistant} />
          <AiSection m={metrics.data} />
          <BusinessSection m={metrics.data} />
        </>
      )}
    </div>
  );
}

function KillSwitch({ token, status }: { token: string; status: AssistantControl }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const toggle = useMutation({
    mutationFn: (enabled: boolean) =>
      adminCall<AssistantControl>(token, "/ai-assistant", {
        method: "PUT",
        body: JSON.stringify({ enabled, reason: enabled ? null : reason.trim() || null }),
      }),
    onSuccess: () => {
      setConfirming(false);
      setReason("");
      queryClient.invalidateQueries({ queryKey: ["dev-metrics"] });
    },
  });

  return (
    <section className="card space-y-4 p-5" aria-labelledby="kill-switch">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`size-3 rounded-full ${status.enabled ? "bg-emerald-500" : "bg-red-500"}`} aria-hidden="true" />
          <div>
            <h2 id="kill-switch" className="font-semibold">
              Trợ lý AI: {status.enabled ? "đang hoạt động" : "đang tắt (bảo trì)"}
            </h2>
            {status.updated_at && (
              <p className="text-sm text-muted">
                Thay đổi lần cuối {formatDateTime(status.updated_at)}
                {status.reason && <> · Lý do: {status.reason}</>}
              </p>
            )}
          </div>
        </div>
        {!status.enabled && (
          <button type="button" className="btn-primary" disabled={toggle.isPending} onClick={() => toggle.mutate(true)}>
            {toggle.isPending ? "Đang bật..." : "Bật lại Trợ lý AI"}
          </button>
        )}
      </div>

      {status.enabled ? (
        <div className="space-y-3">
          <label className="block space-y-1 text-sm">
            <span className="font-medium">Lý do tắt (bắt buộc, ít nhất 5 ký tự; ghi vào audit log)</span>
            <input
              className="input w-full"
              maxLength={300}
              placeholder="vd. Model trả lời sai hàng loạt, nhà cung cấp model lỗi..."
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                setConfirming(false);
              }}
            />
          </label>
          {confirming ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm">Người mua sẽ không chat được với AI cho tới khi bật lại. Chắc chắn tắt?</span>
              <button
                type="button"
                className="btn-sm btn bg-red-600 text-white hover:bg-red-700"
                disabled={toggle.isPending}
                onClick={() => toggle.mutate(false)}
              >
                {toggle.isPending ? "Đang tắt..." : "Tắt ngay"}
              </button>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(false)}>
                Thôi
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn-danger"
              // The API refuses to turn it off without a reason
              disabled={reason.trim().length < 5}
              onClick={() => setConfirming(true)}
            >
              Tắt Trợ lý AI (kill switch)
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-1 text-sm">
          <p className="font-medium">Khung chat của người mua đang hiện:</p>
          <p className="rounded-lg bg-red-50 p-3 text-red-900">{status.message}</p>
          <p className="text-muted">Đặt lịch, xác nhận lịch và các chức năng khác vẫn chạy bình thường.</p>
        </div>
      )}
      {toggle.isError && <ErrorBox error={toggle.error} />}
    </section>
  );
}

const number = new Intl.NumberFormat("vi-VN");
const fmt = (n: number) => number.format(n);
const seconds = (ms: number | null) => (ms == null ? "–" : `${(ms / 1000).toFixed(1)} s`);
// A turn costs fractions of a cent, so small amounts keep 4 decimals
const usd = (n: number | null) => (n == null ? "–" : `$${n < 1 ? n.toFixed(4) : n.toFixed(2)}`);

function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "danger" }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone === "danger" ? "text-red-700" : ""}`}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function AiSection({ m }: { m: DevMetrics }) {
  const ai = m.ai;
  const highErrors = ai.turns > 0 && ai.error_rate >= 0.05;
  const cost = ai.cost;
  return (
    <section className="space-y-4" aria-labelledby="ai-metrics">
      <h2 id="ai-metrics" className="text-lg font-semibold">
        Trợ lý AI · {m.days === 1 ? "24 giờ qua" : `${m.days} ngày qua`}
      </h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Stat label="Lượt chat" value={fmt(ai.turns)} hint={`${fmt(ai.guest_turns)} từ khách chưa đăng nhập · ${fmt(ai.conversations)} hội thoại`} />
        <Stat
          label="Lỗi"
          value={`${(ai.error_rate * 100).toFixed(1)}%`}
          hint={`${fmt(ai.errors)} lượt lỗi${highErrors ? " · cao, xem bên dưới" : ""}`}
          tone={highErrors ? "danger" : undefined}
        />
        <Stat label="Độ trễ p50 / p95" value={`${seconds(ai.latency_p50_ms)} / ${seconds(ai.latency_p95_ms)}`} hint="Lượt thành công" />
        <Stat
          label="Token vào / ra"
          value={`${fmt(ai.prompt_tokens)} / ${fmt(ai.completion_tokens)}`}
          hint={`${fmt(ai.llm_calls)} lần gọi model · ${fmt(ai.tool_calls)} lần gọi công cụ`}
        />
        {/* Token vào counts the whole prompt; this is the part Claude read from its cache (billed far cheaper) */}
        <Stat
          label="Token từ cache"
          value={ai.prompt_tokens ? `${((ai.cache_read_tokens / ai.prompt_tokens) * 100).toFixed(0)}%` : "–"}
          hint={`${fmt(ai.cache_read_tokens)} / ${fmt(ai.prompt_tokens)} token vào đọc từ cache`}
        />
        <Stat
          label="Chi phí TB / lượt"
          value={usd(cost.per_turn_usd)}
          hint={
            cost.total_usd == null
              ? "Model đang dùng chưa có giá (đặt LLM_PRICES)"
              : `Tổng ${usd(cost.total_usd)} · ${fmt(cost.priced_turns)} lượt${cost.unpriced_turns ? ` · ${fmt(cost.unpriced_turns)} lượt chưa có giá` : ""}`
          }
        />
      </div>

      <div className="card p-4">
        <h3 className="mb-3 text-sm font-semibold">Lượt chat mỗi ngày</h3>
        <DailyChart daily={ai.daily} />
      </div>

      <Table
        title="Chi phí theo model"
        head={["Model", "Lượt", "Token TB / lượt (vào · từ cache · ra)", "Chi phí TB / lượt", "Tổng"]}
        rows={cost.by_model.map((row) => {
          const per = (n: number) => fmt(Math.round(n / row.turns));
          return [
            <code key="m">{row.model ?? "?"}</code>,
            fmt(row.turns),
            `${per(row.prompt_tokens)} · ${per(row.cache_read_tokens)} · ${per(row.completion_tokens)}`,
            row.cost_usd == null ? <span key="c" className="text-muted">chưa có giá</span> : usd(row.cost_usd / row.turns),
            usd(row.cost_usd),
          ];
        })}
        empty="Chưa có lượt nào ghi nhận token."
        footer="Ước tính theo giá USD / 1 triệu token (src/services/llm_pricing.py; model khác thêm bằng LLM_PRICES). Token ghi vào cache tính như token vào thường; chỉ tính model của agent trong trace, không tính giám khảo AI."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Table
          title="Công cụ của agent"
          head={["Công cụ", "Lần gọi", "Lỗi"]}
          rows={ai.tools.map((t) => [
            <code key="n">{t.name}</code>,
            fmt(t.calls),
            <span key="f" className={t.failed ? "text-red-700" : undefined}>{fmt(t.failed)}</span>,
          ])}
          empty="Chưa có lần gọi công cụ nào."
        />
        <Table
          title={`Guardrail · ${fmt(m.guardrails.turns_flagged)} lượt bị can thiệp, ${fmt(m.guardrails.blocked_inputs)} tin bị chặn`}
          head={["Loại", "Số lần"]}
          rows={m.guardrails.flags.map((f) => [<code key="f">{f.flag}</code>, fmt(f.count)])}
          empty="Guardrail chưa phải can thiệp."
        />
      </div>

      <Table
        title="Lỗi gần đây"
        head={["Thời điểm", "Loại lỗi", "Chi tiết", "Trace"]}
        rows={ai.recent_errors.map((e) => [
          formatDateTime(e.created_at),
          <code key="t">{e.error_type ?? "?"}</code>,
          <span key="m" className="line-clamp-2 text-muted">
            {e.error_message ?? "–"}
            {e.guest && " · khách"}
          </span>,
          <code key="id" className="select-all text-xs" title="python scripts/ai_traces.py show <trace>">
            {e.trace_id}
          </code>,
        ])}
        empty="Không có lỗi nào trong khoảng này."
        footer={
          ai.error_types.length > 0 &&
          `Theo loại: ${ai.error_types.map((t) => `${t.type} × ${t.count}`).join(", ")}. Xem chi tiết: python scripts/ai_traces.py show <trace>`
        }
      />
    </section>
  );
}

/** Turns per day, one bar each; hover (or focus) a bar for the day's turns and failures. */
function DailyChart({ daily }: { daily: DevMetrics["ai"]["daily"] }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...daily.map((d) => d.turns));
  const label = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  const every = Math.ceil(daily.length / 10);
  const shown = active != null ? daily[active] : null;

  return (
    <div>
      <p className="mb-2 h-5 text-sm text-muted" aria-live="polite">
        {shown
          ? `${label(shown.date)}: ${fmt(shown.turns)} lượt · ${fmt(shown.errors)} lỗi`
          : `Cao nhất ${fmt(max)} lượt/ngày · rê chuột vào cột để xem chi tiết`}
      </p>
      <div className="flex h-40 items-end gap-[2px] border-b border-line" onMouseLeave={() => setActive(null)}>
        {daily.map((d, i) => (
          <button
            key={d.date}
            type="button"
            className="group flex h-full flex-1 items-end focus:outline-none"
            aria-label={`${label(d.date)}: ${d.turns} lượt, ${d.errors} lỗi`}
            onMouseEnter={() => setActive(i)}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
          >
            <span
              className={`block w-full rounded-t ${active === i ? "bg-brand-700" : "bg-brand-500"} group-focus-visible:ring-2 group-focus-visible:ring-brand-200`}
              style={{ height: d.turns ? `${Math.max(2, (d.turns / max) * 100)}%` : 0 }}
            />
          </button>
        ))}
      </div>
      <div className="mt-1 flex gap-[2px] text-[11px] text-muted">
        {daily.map((d, i) => (
          <span key={d.date} className="flex-1 text-center">
            {i % every === 0 || i === daily.length - 1 ? label(d.date) : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function Table({
  title,
  head,
  rows,
  empty,
  footer,
}: {
  title: string;
  head: string[];
  rows: ReactNode[][];
  empty: string;
  footer?: ReactNode;
}) {
  return (
    <div className="card overflow-hidden">
      <h3 className="border-b border-line px-4 py-3 text-sm font-semibold">{title}</h3>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">{empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                {head.map((h, i) => (
                  <th key={h} className={`px-4 py-2 font-medium ${i > 0 && i < 3 && head.length <= 3 ? "text-right" : ""}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r} className="border-t border-line">
                  {row.map((cell, i) => (
                    <td key={i} className={`px-4 py-2 align-top ${i > 0 && head.length <= 3 ? "text-right tabular-nums" : ""}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {footer && <p className="border-t border-line px-4 py-2 text-xs text-muted">{footer}</p>}
    </div>
  );
}

function Breakdown({ title, counts, labels }: { title: string; counts: Record<string, number>; labels?: Record<string, string> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-sm tabular-nums text-muted">{fmt(total)}</span>
      </div>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">Không có.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {entries.map(([key, n]) => (
            <li key={key} className="flex justify-between gap-3">
              <span className="truncate" title={key}>
                {labels?.[key] ?? key}
              </span>
              <span className="tabular-nums">{fmt(n)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BusinessSection({ m }: { m: DevMetrics }) {
  const b = m.business;
  const period = m.days === 1 ? "24 giờ qua" : `${m.days} ngày qua`;
  return (
    <section className="space-y-4" aria-labelledby="business-metrics">
      <h2 id="business-metrics" className="text-lg font-semibold">
        Nghiệp vụ
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Breakdown
          title={`Yêu cầu xem nhà mới · ${period}`}
          counts={b.bookings_by_status}
          labels={BOOKING_STATUS}
        />
        <Breakdown title={`Deal mới · ${period}`} counts={b.deals_by_status} labels={DEAL_STATUS} />
        <Breakdown title="Ca ngoại lệ đang mở" counts={b.open_escalations_by_type} />
        <Breakdown
          title="Tin đăng (hiện tại)"
          counts={b.properties_by_status}
          labels={PROPERTY_STATUS}
        />
        <Breakdown title="Tài khoản" counts={b.users_by_role} labels={ROLE} />
      </div>
    </section>
  );
}
